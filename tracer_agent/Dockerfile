# ═══════════════════════════════════════════════════════════════════
# Purple Agent — The Panopticon Protocol
# Production Image: Multi-arch | Python 3.11 | TCMalloc | Non-root
# Build: docker build -t purple-agent .
# Run:   docker run -p 8080:8080 --env-file .env purple-agent
# ═══════════════════════════════════════════════════════════════════

# --- Stage 1: Builder -------------------------------------------
# Installs all dependencies and downloads spaCy model.
# Only site-packages and binaries are carried to the runtime stage.
FROM python:3.11-slim AS builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgoogle-perftools-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install production dependencies only (slimmer image)
COPY requirements-prod.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements-prod.txt

# Download spaCy model into the install prefix
# [MED-07] v3.0: stderr is NOT suppressed — build failures must be visible
# Note: /install/bin/python does NOT exist (pip --prefix doesn't copy the
# interpreter binary). Use the system python with PYTHONPATH instead, and
# install the model wheel directly from the spaCy GitHub releases.
RUN pip install --no-cache-dir --prefix=/install \
    https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

# --- Stage 2: Runtime -------------------------------------------
FROM python:3.11-slim

# Install TCMalloc runtime library (available on both amd64 and arm64)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libtcmalloc-minimal4 && \
    rm -rf /var/lib/apt/lists/*

# [CRIT-02] Detect TCMalloc library path at build time.
# This works on both amd64 (/usr/lib/x86_64-linux-gnu/) and
# arm64 (/usr/lib/aarch64-linux-gnu/) without hardcoding.
RUN TCMALLOC_PATH=$(find /usr/lib -name "libtcmalloc_minimal.so.4" 2>/dev/null | head -1) && \
    if [ -n "$TCMALLOC_PATH" ]; then \
    echo "TCMALLOC_PATH=$TCMALLOC_PATH" > /etc/tcmalloc.env; \
    echo "Detected TCMalloc at: $TCMALLOC_PATH"; \
    else \
    echo "WARNING: TCMalloc not found, proceeding without it"; \
    echo "TCMALLOC_PATH=" > /etc/tcmalloc.env; \
    fi

# Create non-root user (UID 1000 — standard convention)
RUN groupadd --gid 1000 agent && \
    useradd --uid 1000 --gid agent --shell /bin/bash --create-home agent

WORKDIR /app

# Copy installed Python packages from builder
# [CRIT-01] This single COPY carries ALL packages INCLUDING the spaCy
# model and its dist-info metadata. No separate model copy needed.
COPY --from=builder /install/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /install/bin /usr/local/bin

# Copy application code (respects .dockerignore)
# [MED-06] v3.0: --chown in COPY eliminates redundant chown -R layer
COPY --chown=agent:agent . .

# Create namespace symlink: 'from tracer_agent.src.xxx' resolves via
# /app/tracer_agent/ -> /app/ -> /app/src/xxx.py
RUN ln -s /app /app/tracer_agent

# Environment: determinism + performance + logging
ENV PYTHONHASHSEED=0 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# [HIGH-07] v3.0: LD_PRELOAD is set by ralph.sh sourcing /etc/tcmalloc.env
# at runtime (D2-E). Docker containers do NOT read /etc/environment.
# For non-ralph.sh invocations (e.g., docker run --entrypoint python),
# pass --env LD_PRELOAD=<path> explicitly.

# Make entrypoint executable
# Strip Windows CRLF line endings — #!/bin/bash\r causes "exec: no such file"
RUN sed -i 's/\r$//' ralph.sh && \
    chmod +x ralph.sh && \
    chmod +x scripts/preflight.sh 2>/dev/null || true

# Ensure writable dirs for ralph_runner (runs as non-root agent user)
# Windows source files may lack write permission — chmod fixes this
RUN mkdir -p /app/plans /app/state && \
    chown -R agent:agent /app/plans /app/state && \
    chmod 755 /app/plans /app/state

# Switch to non-root user
USER agent

# Expose A2A server port
EXPOSE 8080

# Health check: lightweight Python probe
# Interval: 30s, Timeout: 5s, Retries: 3, Start period: 10s
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Graceful shutdown: SIGTERM propagates through ralph.sh to Python
# [HIGH-04] Explicit STOPSIGNAL ensures Docker sends SIGTERM (not SIGKILL)
STOPSIGNAL SIGTERM

# Entrypoint: ralph.sh die-and-restart supervision loop
ENTRYPOINT ["./ralph.sh"]
