#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# ARGUS Production Launcher
# Builds frontend, copies dist to backend/static, starts single uvicorn.
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}═══ ARGUS Production Build ═══${NC}"
echo ""

# ── Build frontend ──
echo -e "${YELLOW}Building frontend...${NC}"
cd "$SCRIPT_DIR/frontend"
npm run build
echo -e "  ${GREEN}Frontend built${NC}"

# ── Copy dist to backend/static ──
echo -e "${YELLOW}Copying dist to backend/static...${NC}"
rm -rf "$SCRIPT_DIR/backend/static"
cp -r "$SCRIPT_DIR/frontend/dist" "$SCRIPT_DIR/backend/static"
echo -e "  ${GREEN}Static files ready${NC}"

# ── Start production server ──
echo ""
echo -e "${GREEN}═══ Starting ARGUS (production) ═══${NC}"
echo -e "  ${CYAN}http://localhost:8000${NC}"
echo ""

cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT"
export ARGUS_ENV=production

exec python -m uvicorn argus-app.backend.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers 1
