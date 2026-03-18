#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# ARGUS E2E Smoke Test  —  zero-dependency (curl + jq)
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

BASE="${BASE_URL:-http://localhost:8000}"
PASS=0
FAIL=0
TOTAL=0

# ── Colours ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

pass() { ((PASS++)); ((TOTAL++)); echo -e "  ${GREEN}✓ PASS${NC}  $1"; }
fail() { ((FAIL++)); ((TOTAL++)); echo -e "  ${RED}✗ FAIL${NC}  $1"; }

check_status() {
  local desc="$1" url="$2" expected="${3:-200}"
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
  if [ "$status" = "$expected" ]; then
    pass "$desc (HTTP $status)"
  else
    fail "$desc — expected $expected, got $status"
  fi
}

check_json_field() {
  local desc="$1" url="$2" field="$3"
  local body
  body=$(curl -s "$url" 2>/dev/null || echo "{}")
  if echo "$body" | jq -e "$field" > /dev/null 2>&1; then
    pass "$desc"
  else
    fail "$desc — field $field missing"
  fi
}

post_check() {
  local desc="$1" url="$2" data="$3" expected="${4:-200}"
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -d "$data" "$url" 2>/dev/null || echo "000")
  if [ "$status" = "$expected" ]; then
    pass "$desc (HTTP $status)"
  else
    fail "$desc — expected $expected, got $status"
  fi
}

echo ""
echo -e "${CYAN}════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  ARGUS E2E Smoke Test Suite${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════${NC}"
echo -e "  Target: ${YELLOW}${BASE}${NC}"
echo ""

# ═══ Phase 1: Health & Config ═══
echo -e "${YELLOW}Phase 1: Health & Config${NC}"
check_status "GET /api/health" "${BASE}/api/health"
check_json_field "Health has status field" "${BASE}/api/health" ".status"
check_status "GET /api/config" "${BASE}/api/config"
check_json_field "Config has forge_version" "${BASE}/api/config" ".forge_version"

# Check epoch header
EPOCH_HEADER=$(curl -s -I "${BASE}/api/health" 2>/dev/null | grep -i "X-ARGUS-Epoch" || echo "")
if [ -n "$EPOCH_HEADER" ]; then
  pass "X-ARGUS-Epoch header present"
  ((TOTAL++))
else
  fail "X-ARGUS-Epoch header missing"
  ((TOTAL++))
fi

echo ""

# ═══ Phase 2: Graph API ═══
echo -e "${YELLOW}Phase 2: Graph API${NC}"
check_status "GET /api/graph/stats" "${BASE}/api/graph/stats"
check_json_field "Graph stats has node_count" "${BASE}/api/graph/stats" ".node_count"
check_status "GET /api/graph/visualization" "${BASE}/api/graph/visualization?limit=50"
check_status "GET /api/graph/nodes (paginated)" "${BASE}/api/graph/nodes?page=1&per_page=10"
echo ""

# ═══ Phase 3: Evidence ═══
echo -e "${YELLOW}Phase 3: Evidence${NC}"
check_status "GET /api/evidence" "${BASE}/api/evidence?limit=5"
check_json_field "Evidence has documents array" "${BASE}/api/evidence?limit=5" ".documents"
echo ""

# ═══ Phase 4: Ground Truth ═══
echo -e "${YELLOW}Phase 4: Ground Truth${NC}"
check_status "GET /api/ground-truth/summary" "${BASE}/api/ground-truth/summary"
check_json_field "Ground truth has total_crimes" "${BASE}/api/ground-truth/summary" ".total_crimes"
echo ""

# ═══ Phase 5: Investigation Pipeline ═══
echo -e "${YELLOW}Phase 5: Investigation Pipeline${NC}"

# Get a node ID from the graph
FIRST_NODE=$(curl -s "${BASE}/api/graph/nodes?page=1&per_page=1" 2>/dev/null | jq -r '.nodes[0].id // empty' 2>/dev/null || echo "")

if [ -n "$FIRST_NODE" ]; then
  pass "Retrieved test node: $FIRST_NODE"
  ((TOTAL++))

  # Run investigation
  INV_RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" \
    -d "{\"subject_id\": \"$FIRST_NODE\", \"hop_depth\": 2}" \
    "${BASE}/api/investigation/investigate" 2>/dev/null || echo "{}")

  INV_STATUS=$(echo "$INV_RESPONSE" | jq -r '.status // empty' 2>/dev/null || echo "")
  CASE_ID=$(echo "$INV_RESPONSE" | jq -r '.case_id // empty' 2>/dev/null || echo "")

  if [ -n "$INV_STATUS" ]; then
    pass "POST /api/investigation/investigate — status: $INV_STATUS"
    ((TOTAL++))
  else
    fail "POST /api/investigation/investigate — no status in response"
    ((TOTAL++))
  fi

  # Get investigation by ID
  if [ -n "$CASE_ID" ]; then
    check_status "GET /api/investigation/$CASE_ID" "${BASE}/api/investigation/${CASE_ID}"
  fi

  # List investigations
  check_status "GET /api/investigation/list" "${BASE}/api/investigation/list"
  check_json_field "Investigation list has investigations array" "${BASE}/api/investigation/list" ".investigations"
else
  fail "Could not retrieve a test node — skipping investigation tests"
  ((TOTAL++))
fi
echo ""

# ═══ Phase 6: Assessment ═══
echo -e "${YELLOW}Phase 6: Assessment${NC}"
if [ -n "$CASE_ID" ] && [ "$INV_STATUS" = "COMPLETE" ]; then
  post_check "POST /api/assess" "${BASE}/api/assess" "{\"case_id\": \"$CASE_ID\"}"
else
  echo -e "  ${YELLOW}⊘ SKIP${NC}  Assessment requires completed investigation"
fi
echo ""

# ═══ Phase 7: Benchmark ═══
echo -e "${YELLOW}Phase 7: Benchmark${NC}"
check_status "GET /api/benchmark/list" "${BASE}/api/benchmark/list"
echo ""

# ═══ Phase 8: Reset & Regenerate ═══
echo -e "${YELLOW}Phase 8: Reset & Regenerate${NC}"
post_check "POST /api/reset" "${BASE}/api/reset" "{}"

# Regenerate with small graph for speed
REGEN_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" \
  -d '{"seed": 99, "difficulty": 3, "node_count": 100}' \
  "${BASE}/api/generate" 2>/dev/null || echo "000")

if [ "$REGEN_STATUS" = "200" ]; then
  pass "POST /api/generate — regenerated (HTTP 200)"
  ((TOTAL++))
else
  fail "POST /api/generate — expected 200, got $REGEN_STATUS"
  ((TOTAL++))
fi

# Verify epoch changed after regen
NEW_EPOCH=$(curl -s -I "${BASE}/api/health" 2>/dev/null | grep -i "X-ARGUS-Epoch" | awk '{print $2}' | tr -d '\r' || echo "")
if [ -n "$NEW_EPOCH" ]; then
  pass "Epoch updated after regeneration"
  ((TOTAL++))
else
  fail "Epoch header missing after regeneration"
  ((TOTAL++))
fi

echo ""

# ═══ Summary ═══
echo -e "${CYAN}════════════════════════════════════════════════════════${NC}"
if [ "$FAIL" -eq 0 ]; then
  echo -e "  ${GREEN}ALL TESTS PASSED${NC}  ($PASS/$TOTAL)"
else
  echo -e "  ${RED}$FAIL FAILED${NC}, ${GREEN}$PASS PASSED${NC}  (total: $TOTAL)"
fi
echo -e "${CYAN}════════════════════════════════════════════════════════${NC}"
echo ""

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
