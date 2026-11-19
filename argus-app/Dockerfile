# ═══════════════════════════════════════════════════════════════════
# ARGUS Research & Synthetic Demo Runtime — Multi-stage Non-Root Build
# Used by render.yaml (Render web service) and synthetic demo deployments.
# For the isolated PostgreSQL 16 + OIDC institutional production workbench
# (zero research routes, zero AI deps), use argus-app/Dockerfile.prod.
# Build context: project root (docker build -f argus-app/Dockerfile .)
# ═══════════════════════════════════════════════════════════════════

# ── Stage 1: Build self-hosted React frontend (Node 22 LTS for Vite 8) ──
FROM node:22-alpine AS frontend-build
WORKDIR /build
COPY argus-app/frontend/package.json argus-app/frontend/package-lock.json ./
RUN npm ci
COPY argus-app/frontend/ ./
RUN npm run build

# ── Stage 2: Python 3.12 research runtime (Forge + Tracer + Unified API) ──
FROM python:3.12-slim AS runtime
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY argus-app/backend/requirements.txt /tmp/requirements.txt
RUN PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=10 pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt
RUN PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=10 python -m spacy download en_core_web_sm

# Copy Forge, Tracer, and unified research backend
COPY src/ /app/src/
COPY tracer_agent/ /app/tracer_agent/
COPY argus-app/backend/ /app/argus-app/backend/

# Copy self-hosted frontend build output
COPY --from=frontend-build /build/dist /app/argus-app/backend/static

ENV PYTHONPATH=/app \
    ARGUS_ENV=production \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0 \
    PORT=8000 \
    UNIFIED_MODE=true

RUN groupadd -g 1000 appuser && useradd -u 1000 -g appuser -d /app appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
  CMD sh -c "curl -fsS http://127.0.0.1:${PORT:-8000}/api/health || exit 1"

CMD ["sh", "-c", "exec python -m uvicorn argus-app.backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
