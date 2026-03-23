# ARGUS Frontend

Interactive React frontend for the ARGUS financial crime investigation platform. Provides graph visualization, investigation workflows, SAR viewing, and assessment scoring.

---

## Tech Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| React | 19.2.4 | UI framework |
| Vite | 8.0.0 | Bundler with HMR |
| D3.js | 7.9.0 | Canvas-based graph visualization |
| TailwindCSS | 3.4.19 | Utility-first styling |
| Framer Motion | 12.36.0 | Animation and transitions |
| Recharts | 3.8.0 | Charting (assessment rubric) |
| Lucide React | 0.577.0 | Icon library |
| React Router | 7.13.1 | Client-side routing |
| Vitest | 4.1.0 | Testing framework |

---

## Development

```bash
cd argus-app/frontend

# Install dependencies
npm install

# Development server (HMR, proxies /api to localhost:8000)
npm run dev
# Available at http://localhost:5173

# Production build
npm run build

# Run tests
npm run test

# Lint
npm run lint

# Preview production build
npm run preview
```

---

## Pages (9 Routes)

| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | Health checks, graph stats, hero banner |
| `/graph` | Graph Explorer | Interactive D3.js network visualization with pan/zoom |
| `/investigate` | Investigation | Run AML investigations with 8-step pipeline tracker |
| `/sar` | SAR Viewer | View generated SARs (FinCEN + FIU-IND dual format) |
| `/evidence` | Evidence Browser | Search evidence documents (keyword, type, entity filter) |
| `/assessment` | Assessment | Investigation quality scoring with rubric breakdown |
| `/benchmark` | Benchmark | All-node investigation with detection accuracy metrics |
| `/vision` | Vision | Product marketing page (problem, solution, roadmap) |
| `/settings` | Settings | Backend configuration, data generation, system health |

---

## Component Architecture

### Shared Components (16)

| Component | Purpose |
|-----------|---------|
| `Layout` | Sidebar navigation (desktop/mobile), top nav, router outlet |
| `PageHeader` | Page title, subtitle, optional action badge |
| `GlowCard` | Elevated card with glow effect |
| `StatCard` | Key metric display (label, value, icon, color) |
| `Toast` | Toast notification container (max 3 visible) |
| `LoadingSpinner` | Animated spinner |
| `ErrorCard` | Error display with retry button |
| `Skeleton` | Placeholder loading state |
| `StatusBadge` | Investigation/process status indicator |
| `ConfidenceBar` | Horizontal progress bar for confidence scores |
| `TypologyBadge` | Crime typology label (structuring/layering) |
| `AccordionSection` | Collapsible content sections |
| `EmptyState` | Placeholder when no data available |
| `AnimatedNumber` | Number countup animation with spring physics |
| `KeyboardShortcutsModal` | Help modal with keyboard shortcuts |
| `StaleStateGuard` | Watches for backend epoch changes, resets cache |

### Domain Components

- **Graph**: `NetworkGraph` (D3.js canvas), `NodeDetailPanel` (slide-in details)
- **Investigation**: `InvestigationForm` (entity search), `PipelineTracker` (8-step), `InvestigationResults`
- **SAR**: `SARDocument` (dual-jurisdiction rendering), `InvestigationListPanel`
- **Assessment**: `ScoreGauge` (animated SVG), `RubricChart` (Recharts)
- **Benchmark**: `BenchmarkConfig`, `BenchmarkProgress`, `BenchmarkResults`
- **Evidence**: `EvidenceCard` (with keyword highlighting)

---

## Graph Visualization

The `NetworkGraph` component uses D3.js with **Canvas rendering** (not SVG) for performance at 5,000+ nodes.

- **Force-directed simulation** for organic layout
- **Quadtree-based hover detection** for interactive node selection
- **Pan/zoom** with D3 zoom behavior
- **Theme-aware colors** via CSS custom properties
- **Visual encoding**:
  - Structuring mule nodes: rose (12px)
  - Structuring source nodes: amber (5px)
  - Layering nodes: violet (6px)
  - Default nodes: neutral (3px)

---

## API Client

`src/api/client.js` wraps all backend communication (17 endpoints under `/api/`).

**Custom `useQuery` hook** (`src/hooks/useQuery.js`):
- In-memory Map-based cache with configurable `staleTime` (default 30s)
- Request deduplication (inflight promise tracking)
- Stale-while-revalidate pattern
- Cache invalidation via `invalidateQueries(prefix)`
- Returns `{ data, error, loading, refetch }`

---

## Design System

**"Forensic Elegance" v6.0** (`src/index.css`)

- **70+ CSS custom properties** for colors, shadows, fonts, animations
- **Surface hierarchy**: 4 levels (white -> slate-200)
- **Status colors**: amber, violet, rose, emerald, cyan
- **Accent**: indigo (#4f46e5)
- **Fonts**: Instrument Serif (display), DM Sans (body), JetBrains Mono (code)
- **Animations**: shimmer, pulse-ring, fade-in
- **Responsive**: Sidebar collapses from 260px -> 72px on mobile

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `?` | Show keyboard shortcuts modal |
| `1-8` | Navigate to pages (Dashboard through Vision) |
| `9` | Settings |
| `Esc` | Close modal/panel |

**Graph Explorer only:**

| Key | Action |
|-----|--------|
| `+` / `=` | Zoom in |
| `-` | Zoom out |
| `0` | Fit to view |
| `Esc` | Deselect node |

---

## File Structure

```
frontend/
+-- src/
|   +-- api/client.js               API wrapper (17 endpoints)
|   +-- components/
|   |   +-- shared/                  16 reusable components
|   |   +-- layout/Layout.jsx        Sidebar + router outlet
|   |   +-- graph/                   NetworkGraph, NodeDetailPanel
|   |   +-- investigation/           Form, PipelineTracker, Results
|   |   +-- sar/                     SARDocument, InvestigationListPanel
|   |   +-- assessment/              ScoreGauge, RubricChart
|   |   +-- benchmark/               Config, Progress, Results
|   |   +-- evidence/                EvidenceCard
|   |   +-- vision/                  8 marketing section components
|   +-- contexts/ToastContext.jsx    Toast notifications
|   +-- hooks/
|   |   +-- useQuery.js              Data fetching + cache
|   |   +-- useHotkeys.js            Keyboard shortcuts
|   +-- pages/                       9 route pages
|   +-- utils/
|   |   +-- format.js                Number/currency/time formatting
|   |   +-- highlightContent.jsx     Search term highlighting
|   +-- App.jsx                      Router configuration
|   +-- main.jsx                     React entry point
|   +-- index.css                    Design system (Forensic Elegance v6.0)
+-- public/
|   +-- favicon.svg                  App logo (shield)
|   +-- icons.svg                    Icon sprite
+-- index.html                       SPA root (fonts, meta)
+-- vite.config.js                   Bundler + API proxy config
+-- vitest.config.js                 Test runner config
+-- tailwind.config.js               CSS theme variables
+-- postcss.config.js                CSS pipeline
+-- eslint.config.js                 Linting rules
+-- package.json                     Dependencies
```
