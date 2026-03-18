#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# ARGUS Development Launcher
# Starts backend (uvicorn) and frontend (vite) with health gate.
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colours
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  echo -e "${YELLOW}Shutting down...${NC}"
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null && echo "  Frontend stopped"
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null && echo "  Backend stopped"
  exit 0
}
trap cleanup INT TERM

echo -e "${CYAN}═══ ARGUS Development Server ═══${NC}"
echo ""

# ── Start backend ──
echo -e "${YELLOW}Starting backend...${NC}"
cd "$PROJECT_ROOT"
PYTHONPATH="$PROJECT_ROOT" python -m uvicorn argus-app.backend.main:app \
  --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo -e "  Backend PID: $BACKEND_PID"

# ── Health gate: wait for backend to be ready ──
echo -e "${YELLOW}Waiting for backend health...${NC}"
MAX_WAIT=30
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health 2>/dev/null || echo "000")
  if [ "$STATUS" = "200" ]; then
    echo -e "  ${GREEN}Backend healthy (${WAITED}s)${NC}"
    break
  fi
  sleep 1
  ((WAITED++))
done

if [ $WAITED -ge $MAX_WAIT ]; then
  echo -e "  ${RED}Backend failed to start within ${MAX_WAIT}s${NC}"
  cleanup
  exit 1
fi

# ── Start frontend ──
echo -e "${YELLOW}Starting frontend...${NC}"
cd "$SCRIPT_DIR/frontend"
npx vite --port 5173 --host &
FRONTEND_PID=$!
echo -e "  Frontend PID: $FRONTEND_PID"

echo ""
echo -e "${GREEN}═══ ARGUS running ═══${NC}"
echo -e "  Backend:  ${CYAN}http://localhost:8000${NC}"
echo -e "  Frontend: ${CYAN}http://localhost:5173${NC}"
echo -e "  Press Ctrl+C to stop"
echo ""

wait
