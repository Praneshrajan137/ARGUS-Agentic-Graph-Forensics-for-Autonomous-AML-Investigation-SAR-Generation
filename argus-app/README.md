# ARGUS Unified App

Full-stack application combining the Forge Agent backend with a React 19 interactive frontend, served on a single port for deployment.

**Version:** 8.0.0
**Port:** 8000

---

## Overview

The unified app integrates graph generation, crime injection, investigation, and assessment into a single FastAPI server with a React frontend. It eliminates the need for Docker Compose multi-agent orchestration -- one process serves everything.

### Architecture

```
+--------------------------------------------------------------+
|                    Unified App (:8000)                         |
+--------------------------------------------------------------+
|                                                                |
|  FastAPI Backend                                               |
|  +----------------------------------------------------------+ |
|  | /api/health       /api/generate      /api/graph/stats     | |
|  | /api/nodes/{id}   /api/transactions  /api/evidence        | |
|  | /api/investigation/submit   /api/assessment/results       | |
|  | /api/benchmark/*  /api/config        /api/agent/*         | |
|  +----------------------------------------------------------+ |
|           |                                                    |
|  +--------v---------+    +-------------------------------+    |
|  | Forge Service     |    | React 19 Frontend (static)    |    |
|  | - Graph Generator |    | - D3.js canvas graph explorer |    |
|  | - Crime Injector  |    | - Investigation pipeline UI   |    |
|  | - Evidence Gen    |    | - SAR viewer (dual format)    |    |
|  | - Assessment      |    | - Assessment scoring          |    |
|  +-------------------+    | - Evidence browser            |    |
|                           +-------------------------------+    |
+--------------------------------------------------------------+
```

---

## Quick Start

### Local Development

```bash
# From project root
cd argus-app

# Backend
pip install -r backend/requirements.txt
python -m backend.main
# API available at http://localhost:8000/api/health

# Frontend (separate terminal, for hot-reload development)
cd frontend
npm install
npm run dev
# UI available at http://localhost:5173 (proxies /api to :8000)
```

### Production (Docker)

```bash
# Build unified image
docker build -f argus-app/Dockerfile -t argus-unified .

# Run
docker run -p 8000:8000 \
    -e GRAPH_SIZE=5000 \
    -e DIFFICULTY=5 \
    -e SEED=42 \
    argus-unified
```

### Render Deployment

The project includes a `render.yaml` in the repository root that deploys the unified app:

```yaml
services:
  - type: web
    name: argus
    runtime: docker
    dockerfilePath: argus-app/Dockerfile
    healthCheckPath: /api/health
    envVars:
      - key: GRAPH_SIZE
        value: "5000"
      - key: DIFFICULTY
        value: "5"
      - key: SEED
        value: "42"
```

---

## API Endpoints

All endpoints are prefixed with `/api/`.

### Health & Configuration

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Server health status + versions |
| `/api/config` | GET | Current configuration (graph size, difficulty, seed) |
| `/api/agent/card` | GET | Agent capability manifest |
| `/api/agent/config` | GET | Agent detection thresholds |
| `/api/agent/health` | GET | Agent subsystem health |

### Graph & Data

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/generate` | POST | Generate new graph (accepts seed, difficulty, size) |
| `/api/graph/stats` | GET | Graph statistics (nodes, edges, crimes, degree) |
| `/api/graph/visualization` | GET | Full graph data for D3.js rendering |
| `/api/nodes` | GET | Search/list nodes (with query params) |
| `/api/nodes/{id}` | GET | Node details (entity type, risk, connections) |
| `/api/nodes/{id}/transactions` | GET | Node's transaction history |
| `/api/nodes/{id}/connections` | GET | Node's network connections |
| `/api/transactions` | GET | Transaction list (filterable) |
| `/api/evidence` | GET | Evidence document search (keyword, type, entity) |

### Investigation

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/investigation/submit` | POST | Start investigation (subject_id, hop_depth, jurisdiction) |
| `/api/investigations` | GET | List all investigations |
| `/api/investigations/{case_id}` | GET | Get investigation details + SAR |
| `/api/investigation/progress/{case_id}` | GET | Pipeline progress (8 steps) |

### Assessment & Benchmark

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/assessment/results` | GET | Assessment results for a case |
| `/api/assessment/ground-truth` | GET | Ground truth crime data |
| `/api/benchmark/run` | POST | Run all-node benchmark |
| `/api/benchmark/results` | GET | Benchmark results |
| `/api/benchmark/progress` | GET | Benchmark progress |

### State Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/reset` | POST | Reset all state (regenerate graph) |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GRAPH_SIZE` | `5000` | Number of nodes in generated graph |
| `DIFFICULTY` | `5` | Crime injection difficulty (1-10) |
| `SEED` | `42` | Random seed for reproducibility |
| `PORT` | `8000` | Server port |
| `PYTHONPATH` | `/app` | Python module path |
| `PYTHONHASHSEED` | `0` | Deterministic hash iteration |
| `UNIFIED_MODE` | `true` | Enable unified app mode |
| `OPENAI_API_KEY` | (none) | For LLM SAR generation (optional) |
| `ARGUS_ENV` | `development` | Environment (development/production) |

---

## Project Structure

```
argus-app/
+-- Dockerfile                     Multi-stage production build
+-- run.sh                         Local development script
+-- run-prod.sh                    Production startup script
+-- e2e-smoke.sh                   End-to-end smoke test
+-- backend/
|   +-- __init__.py
|   +-- main.py                    FastAPI app (lifespan hook, 17+ routes)
|   +-- config.py                  Imports from Forge + Tracer configs
|   +-- routes/                    API route modules
|   +-- services/
|   |   +-- forge_service.py       Graph generation + crime injection
|   +-- models/
|   |   +-- state.py               In-memory state management
|   |   +-- schemas.py             Pydantic request/response models
|   +-- requirements.txt           Backend dependencies
|   +-- test_imports.py            Import smoke test
+-- frontend/                      React 19 application
    +-- src/                       (see frontend/README.md)
    +-- vite.config.js             Vite bundler + API proxy
    +-- package.json               Dependencies
```

---

## Key Design Decisions

- **Single Process**: Backend generates graph on startup via lifespan hook, serves both API and static frontend
- **Epoch-Based Cache Invalidation**: Backend tracks data generation epoch; frontend detects changes via custom `argus:epoch-change` event
- **Credential Redaction**: All API keys and secrets are redacted from log output
- **Decimal Serialization**: Monetary amounts use `Decimal` internally, serialized via `json.dumps(default=str)`
