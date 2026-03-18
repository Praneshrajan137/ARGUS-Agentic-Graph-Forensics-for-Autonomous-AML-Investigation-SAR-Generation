"""Pydantic v2 request/response models.

All monetary values serialize as float (Decimal → float at boundary).
All node IDs are strings. All timestamps are Unix epoch integers.
"""
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from decimal import Decimal
from typing import Any

# ═══ HEALTH ═══

class HealthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str = "ok"
    forge_version: str
    tracer_version: str
    unified_version: str
    graph_loaded: bool
    node_count: int = 0
    edge_count: int = 0
    uptime_seconds: float = 0.0

# ═══ GENERATION ═══

class GenerateRequest(BaseModel):
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    difficulty: int = Field(default=5, ge=1, le=10)
    node_count: int = Field(default=1000, ge=50, le=10000, alias="graph_size")

    model_config = ConfigDict(populate_by_name=True)

class GenerateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str
    node_count: int
    edge_count: int
    crimes_injected: int
    evidence_count: int
    seed: int
    difficulty: int
    generated_at: str

# ═══ GRAPH DATA ═══

class CrimeSummary(BaseModel):
    crime_type: str
    node_count: int
    edge_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)

class GraphStatsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    node_count: int
    edge_count: int
    density: float
    avg_degree: float
    crime_summary: list[CrimeSummary] = Field(default_factory=list)
    seed: int
    difficulty: int
    generated_at: str | None = None

class NodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    entity_type: str
    jurisdiction: str
    risk_score: float = 0.0
    risk_rating: str = "low"
    degree: int = 0
    in_degree: int = 0
    out_degree: int = 0
    is_criminal: bool = False
    crime_type: str | None = None
    swift_code: str = ""
    ifsc_code: str = ""
    pan_number: str = ""
    address: str = ""
    account_id: str = ""

class NodeListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    nodes: list[NodeResponse]
    total: int
    page: int
    per_page: int
    total_pages: int

class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    source: str
    target: str
    amount: float
    currency: str = "USD"
    transaction_type: str = ""
    timestamp: int = 0
    label: str = "legitimate"

    @field_serializer("amount")
    def serialize_amount(self, v: Any) -> float:
        if isinstance(v, Decimal):
            return float(v)
        return float(v) if v is not None else 0.0

class ConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    node_id: str
    name: str
    direction: str  # "inbound" | "outbound"
    transaction_count: int
    total_amount: float
    entity_type: str = ""

# ═══ GRAPH VISUALIZATION ═══

class GraphNodeViz(BaseModel):
    """Node for D3 force graph visualization."""
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    group: str  # "legitimate" | "structuring_source" | "structuring_mule" | "layering"
    entity_type: str = ""
    risk_rating: str = "low"
    degree: int = 0

class GraphEdgeViz(BaseModel):
    """Edge for D3 force graph visualization."""
    model_config = ConfigDict(from_attributes=True)
    source: str
    target: str
    label: str = "legitimate"  # "legitimate" | "structuring" | "layering"
    amount: float = 0.0
    currency: str = "USD"

    @field_serializer("amount")
    def serialize_amount(self, v: Any) -> float:
        if isinstance(v, Decimal):
            return float(v)
        return float(v) if v is not None else 0.0

class GraphVisualizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    nodes: list[GraphNodeViz]
    edges: list[GraphEdgeViz]
    node_count: int
    edge_count: int

# ═══ EVIDENCE ═══

class EvidenceDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str = ""
    source_type: str = ""
    content: str = ""
    subject_id: str = ""
    associated_entity: str = ""
    timestamp: int = 0
    crime_type: str = ""

class EvidenceListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    documents: list[EvidenceDocumentResponse]
    total: int

# ═══ INVESTIGATION ═══

class InvestigationRequest(BaseModel):
    subject_id: str
    hop_depth: int = Field(default=3, ge=1, le=10)
    jurisdiction: str = Field(default="fincen", pattern="^(fincen|fiu_ind)$")
    case_id: str | None = None  # auto-generated if None

class PipelineStep(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    status: str  # "pending" | "running" | "complete" | "failed" | "warning"
    duration_ms: int = 0
    detail: str = ""

class InvestigationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    case_id: str
    subject_id: str
    jurisdiction: str
    status: str  # "IN_PROGRESS" | "COMPLETE" | "FAILED"
    detected_typology: str = "NONE"
    involved_entities: list[str] = Field(default_factory=list)
    confidence_score: float = 0.0
    sar_narrative: str = ""
    sar_draft: dict[str, Any] | None = None
    evidence_package: dict[str, Any] | None = None
    detection_results: dict[str, Any] | None = None
    validation_errors: list[str] = Field(default_factory=list)
    idempotency_key: str = ""
    investigation_timestamp: int = 0
    steps: list[PipelineStep] = Field(default_factory=list)
    error: str | None = None

class InvestigationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    investigations: list[InvestigationResponse]
    total: int

class PipelineStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    case_id: str
    status: str
    current_step: str = ""
    steps: list[PipelineStep] = Field(default_factory=list)
    progress_pct: float = 0.0

# ═══ ASSESSMENT ═══

class AssessmentRequest(BaseModel):
    case_id: str

class RubricBreakdown(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    pattern_detection: float = 0.0
    evidence_analysis: float = 0.0
    narrative_quality: float = 0.0
    completeness: float = 0.0
    efficiency: float = 0.0

class AssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    case_id: str
    overall_score: float
    entity_metrics: dict[str, Any] = Field(default_factory=dict)
    rubric_breakdown: RubricBreakdown = Field(default_factory=RubricBreakdown)
    hallucination_check: dict[str, Any] = Field(default_factory=dict)
    hallucination_count: int = 0
    hallucination_details: list[str] = Field(default_factory=list)
    five_ws_validation: dict[str, Any] = Field(default_factory=dict)
    five_ws: dict[str, bool] = Field(default_factory=dict)
    missed_indicators: list[str] = Field(default_factory=list)

# ═══ UTILITY ═══

class GroundTruthSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_crimes: int
    crime_types: list[str]
    total_criminal_nodes: int
    difficulty: int

class ConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    forge_version: str
    tracer_version: str
    unified_version: str
    seed: int
    difficulty: int
    graph_size: int
    structuring_band_usd: str  # "$9,000 – $9,800"
    ctr_threshold_usd: str     # "$10,000"
    layering_decay_range: str  # "2% – 5%"
    min_chain_length: int
    max_dfs_depth: int
    confidence_threshold: float

# ═══ BENCHMARK ═══

class BenchmarkRequest(BaseModel):
    mode: str = Field(default="fast", pattern=r"^(fast|full)$")
    hop_depth: int = Field(default=3, ge=1, le=10)
    jurisdiction: str = Field(default="fincen", pattern=r"^(fincen|fiu_ind)$")
    generate: bool = False
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    difficulty: int = Field(default=5, ge=1, le=10)
    node_count: int = Field(default=1000, ge=50, le=5000)

class BenchmarkNodeResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    node_id: str
    is_crime_node: bool
    expected_typology: str
    detected_typology: str
    correct: bool
    confidence: float
    investigation_case_id: str
    assessment_score: float
    duration_ms: int
    entity_precision: float
    entity_recall: float
    entity_f1: float

class BenchmarkAggregateMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_investigations: int
    completed: int
    failed: int
    structuring_detected: bool
    layering_detected: bool
    crime_detection_rate: float
    false_positive_rate: float
    avg_precision: float
    avg_recall: float
    avg_f1: float
    avg_confidence: float
    avg_assessment_score: float
    total_duration_ms: int
    avg_duration_ms: float
    structuring_detection_rate: float
    layering_detection_rate: float

class BenchmarkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    benchmark_id: str
    status: str
    config: dict[str, Any] = Field(default_factory=dict)
    progress: float = 0.0
    current_node: str = ""
    completed_count: int = 0
    total_count: int = 0
    aggregate: BenchmarkAggregateMetrics | None = None
    node_results: list[BenchmarkNodeResult] = Field(default_factory=list)
    started_at: str = ""
    completed_at: str | None = None

class BenchmarkProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    benchmark_id: str
    status: str
    progress: float = 0.0
    current_node: str = ""
    completed_count: int = 0
    total_count: int = 0

class BenchmarkListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    benchmarks: list[BenchmarkResponse]
    total: int
