═══ ARGUS — MASTER CONTEXT v6.0 ═══

PROJECT: ARGUS: Agentic Graph Forensics for Autonomous AML Investigation & SAR Generation
STATUS: Backend (FORGE + TRACER) COMPLETE. Building unified full-stack application.
FORGE VERSION: 8.0.0 (src/config.py AGENT_VERSION)
TRACER VERSION: 7.0.0 (purple_agent/src/config.py AGENT_VERSION)
UNIFIED APP VERSION: 1.0.0

ARCHITECTURE:
- Backend: Single FastAPI server (port 8000) wrapping FORGE (graph gen, crime injection,
  evidence, assessment) AND TRACER (detection heuristics, SAR template, evidence synthesis)
  into 17 REST endpoints under /api/*
- Frontend: React 18 + Vite + Tailwind CSS v3 + D3.js v7 + Recharts + Lucide React + Framer Motion
- Communication: Frontend fetch() → Vite proxy → FastAPI /api/* endpoints
- State: In-memory AppState singleton (graph, ground_truth, evidence, investigations)
- No Docker required. No microservices. Single process.

MONOREPO LAYOUT (existing code stays in place):
  project_root/
  ├── src/core/                    # FORGE agent
  │   ├── graph_generator.py       # generate_scale_free_graph → returns MultiDiGraph
  │   ├── crime_injector.py        # StructuringConfig, LayeringConfig
  │   ├── evidence_generator.py    # EvidenceGenerator
  │   ├── a2a_interface.py         # DO NOT IMPORT (creates 2nd FastAPI app)
  │   ├── result_types.py          # EntityMetrics, HallucinationCheck, FiveWsValidation — SAFE
  │   └── financial_crime_pb2.py   # Protobuf bindings (use THIS one)
  ├── src/config.py                # Forge config: AGENT_VERSION="8.0.0", all thresholds as Decimal
  ├── purple_agent/src/core/       # TRACER agent (COPY into tracer_service.py)
  ├── argus-app/                   # NEW: unified full-stack application
  │   ├── backend/
  │   └── frontend/

IMPORT STRATEGY (v5.0 COPY approach — unchanged):
  FORGE modules: import normally via sys.path.
  TRACER modules: COPIED into tracer_service.py.
  Assessment functions: COPIED into assessment_service.py.

  CONSTANT REMAPPING (v5.0 D-44/D-45 — 3 aliases):
    from src.config import LAYERING_MIN_DECAY, LAYERING_MAX_DECAY
    DECAY_RATE_MIN = LAYERING_MIN_DECAY   # Decimal("0.02")
    DECAY_RATE_MAX = LAYERING_MAX_DECAY   # Decimal("0.05")
    SPACY_MODEL_NAME = "en_core_web_sm"

  NOTE: VELOCITY_THRESHOLD is a TRACER-only constant (purple_agent/src/config.py).
  It does NOT exist in src/config.py and must be defined locally in tracer_service.py.

GRAPH DATA BRIDGE (v5.0 field mapping — unchanged):
  Edge: transaction_id → id, transaction_type → type (uppercased), timestamp: datetime → int
  Node: int ID → str ID, swift → swift_code, country → jurisdiction
  Node: risk_score (float) → risk_rating (str: low/medium/high)
  Node: entity_type: person → individual, company → business (v5.0 D-48)
  Evidence: body/narrative → content

DESIGN SYSTEM v6.0 — "FORENSIC ELEGANCE" (LIGHT THEME):
  Typography:
    Display/Headings: Instrument Serif (Google Fonts) — editorial authority
    Body/UI: DM Sans (Google Fonts) — geometric clarity, excellent at small sizes
    Data/Mono: JetBrains Mono (Google Fonts) — numbers, IDs, amounts, code

  Color System (CSS custom properties — see DESIGN SYSTEM section):
    Surface hierarchy: white → #f8fafc → #f1f5f9 → #e2e8f0
    Text hierarchy: #0f172a → #334155 → #64748b → #94a3b8
    Accent — Indigo:  #4f46e5 (primary action), #818cf8 (hover), #eef2ff (tint)
    Status — Amber:   #d97706 (structuring), #fef3c7 (tint)
    Status — Violet:  #7c3aed (layering), #ede9fe (tint)
    Status — Rose:    #e11d48 (danger/criminal/mule), #ffe4e6 (tint)
    Status — Emerald: #059669 (success/legitimate), #d1fae5 (tint)
    Status — Cyan:    #0891b2 (info/interactive), #cffafe (tint)
    Chart accents: #f97316, #8b5cf6, #06b6d4, #10b981, #f43f5e, #eab308

  Layout:
    Max content width: 1440px (centered)
    Sidebar: 260px fixed, collapsible to 72px
    Page padding: 32px
    Card radius: 12px, shadow: 0 1px 3px rgba(0,0,0,0.08)
    Section spacing: 32px between major sections, 16px between cards

  Animation (Framer Motion):
    Page entrance: stagger children 50ms, y: 12→0, opacity: 0→1, duration: 0.4s
    Card hover: scale 1.005, shadow elevation, 200ms spring
    Number countup: animated from 0 to value over 800ms with easeOutExpo
    Pipeline steps: sequential reveal 200ms apart with spring physics
    Graph transitions: 600ms spring for node repositioning
    Skeleton loading: shimmer gradient sweep, 1.5s loop

CRITICAL RULES (NON-NEGOTIABLE — unchanged from v5.0):
1. Decimal(str(value)) for ALL monetary amounts — NEVER float
2. NetworkX MultiDiGraph — NEVER DiGraph
3. Iterative DFS — NEVER recursive
4. sorted() on ALL list(set(...)) — deterministic
5. Frontend: ALL data from real API calls — NO mocked data
6. PYTHONHASHSEED=0 for ALL Python processes
7. NEVER import from src.core.a2a_interface
8. Node IDs as STRINGS in all API responses
9. json.dumps(default=str) for Decimal serialization
10. Frontend: ALL components reference CSS custom properties, NEVER raw hex

═══ END MASTER CONTEXT v6.0 ═══
