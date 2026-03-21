# ═══════════════════════════════════════════════════════════════════
# ARGUS — Multi-stage Docker Build
# Build context: project root (docker build -f argus-app/Dockerfile .)
# ═══════════════════════════════════════════════════════════════════

# ── Stage 1: Build frontend ──
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY argus-app/frontend/package.json argus-app/frontend/package-lock.json* ./
RUN npm ci
COPY argus-app/frontend/ ./
RUN npm run build

# ── Stage 2: Python runtime ──
FROM python:3.11-slim AS runtime
WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY argus-app/backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt \
    && python -m spacy download en_core_web_sm

# Copy application code
COPY src/ /app/src/
COPY tracer_agent/ /app/tracer_agent/
COPY argus-app/backend/ /app/argus-app/backend/

# Copy frontend build output
COPY --from=frontend-build /build/dist /app/argus-app/backend/static

# Environment
ENV PYTHONPATH=/app \
    ARGUS_ENV=production \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    UNIFIED_MODE=true

RUN groupadd -g 1000 appuser && useradd -u 1000 -g appuser -d /app appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["python", "-m", "uvicorn", "argus-app.backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
