# ARGUS — Evidence-Linked Financial Graph Investigation & Review Workbench

ARGUS separates two distinct runtimes:

1. **Production Candidate Workbench (`argus-app/backend/production.py` + `worker.py` + React UI)** — designed for one US bank/credit union (~10 concurrent analysts, up to 100,000 canonical transactions per CSV batch, 5 concurrent supervised investigations). Uses PostgreSQL 16, institutional OIDC Authorization Code + PKCE, rotating HTTP-only sessions + CSRF, deterministic detection and Five Ws + How drafting with typed source citations, independent reviewer approval envelopes, immutable byte exports (`REVIEWED PACKAGE — NOT FILED`), and an offline cryptographic verifier. **Zero financial records are sent to external AI services.**
2. **Synthetic Research Runtime (`argus-app/backend/main.py`, `src/` Forge, `tracer_agent/` Tracer)** — preserved separately for synthetic scenario generation, A2A Protobuf benchmarking, and regression testing. Production never mounts `/api/generate`, `/api/reset`, `/api/ground-truth`, `/api/benchmark`, or `/api/assess`.

> **Scope & Limitations:** ARGUS produces reviewed narrative/evidence packages for an institution's existing external filing system. It does **not** perform automatic regulatory filing, does **not** claim comprehensive AML coverage or legal compliance certification, and never treats a graph path as proof of fungible-fund identity or criminal intent.

---

## Local Production Stack (PostgreSQL 16 + Local Test IdP + API + Worker)

Prerequisites: Docker Engine + Docker Compose, Python 3.12, Node 22 LTS.

```bash
# Start PostgreSQL 16, local synthetic OIDC IdP (:9000), Alembic migrator, API (:8000), and worker
docker compose -f argus-app/docker-compose.prod.yml up --build
```

- Workbench UI & API: `http://127.0.0.1:8000` (health: `/api/health/live`, `/api/health/ready`, `/api/health/workers`)
- Local test IdP: `http://127.0.0.1:9000/.well-known/openid-configuration` (never a production bypass; uses real Authorization Code + PKCE + RS256 JWKS)

### Offline Package Verification

```bash
python -m backend.verifier --package ./exported-package-dir --source-dir ./original-csvs
```

Omitting `--source-dir` verifies package digest integrity, approval independence, and embedded arithmetic while explicitly reporting `provenance_status: NOT_CHECKED_ORIGINAL_FILES_NOT_SUPPLIED`.

---

## Verification & Evaluation Commands

### 1. Research Regression Suites (Forge + Tracer)
```bash
PYTHONHASHSEED=0 pytest tests/ -v
PYTHONHASHSEED=0 pytest tracer_agent/tests/ -v
```

### 2. Production Backend & PostgreSQL Contract Suite
```bash
export ARGUS_TEST_DATABASE_URL="postgresql+psycopg://argus_admin:argus_test_password@127.0.0.1:5432/argus_test"
alembic -c argus-app/backend/alembic.ini upgrade head
PYTHONHASHSEED=0 pytest argus-app/backend/tests/ -v
```

### 3. Frontend Lint, Unit/Accessibility Tests & Self-Hosted Build
```bash
cd argus-app/frontend
npm ci
npm run lint
npm test
npm run build
```

### 4. Isolated Backup/Restore Rehearsal & Section 5 Evaluation Reports
```bash
python argus-app/scripts/rehearse_recovery.py --output argus-app/eval/results/recovery_rehearsal.json
python argus-app/eval/run_correctness_eval.py --output argus-app/eval/results/correctness.json
python argus-app/eval/run_detection_eval.py --output argus-app/eval/results/detection.json
python argus-app/eval/run_capacity_eval.py --output argus-app/eval/results/capacity.json
```

---

## Live Release Prerequisites (Outside Code Scope)

Code completion and synthetic tests do not constitute regulatory readiness. Institutional deployment additionally requires approved hosting/residency and institutional OIDC IdP integration, verified source-system semantics and independent upstream reconciliation controls, retained-history capacity sizing, institutional retention/legal-hold policies, independent audit/digest custody, accepted backup RPO/RTO targets, independent security review, adjudicated institutional detection evaluation, and human-factors analyst usability acceptance.
