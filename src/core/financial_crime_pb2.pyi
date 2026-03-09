"""Type stubs for auto-generated protobuf module.

These stubs allow mypy to resolve dynamically-built protobuf message classes.
The actual classes are created at runtime by protobuf's descriptor builder.
"""

from typing import Mapping, Sequence
from google.protobuf.message import Message


class Transaction(Message):
    id: str
    source_node: str
    target_node: str
    amount: float
    currency: str
    timestamp: int
    type: str
    reference: str
    branch_code: str
    def __init__(self, *, id: str = ..., source_node: str = ..., target_node: str = ...,
                 amount: float = ..., currency: str = ..., timestamp: int = ...,
                 type: str = ..., reference: str = ..., branch_code: str = ...) -> None: ...


class NodeAttributes(Message):
    id: str
    name: str
    entity_type: str
    jurisdiction: str
    account_id: str
    ifsc_code: str
    pan_number: str
    address: str
    risk_rating: str
    swift_code: str
    def __init__(self, *, id: str = ..., name: str = ..., entity_type: str = ...,
                 jurisdiction: str = ..., account_id: str = ..., ifsc_code: str = ...,
                 pan_number: str = ..., address: str = ..., risk_rating: str = ...,
                 swift_code: str = ...) -> None: ...


class TextEvidence(Message):
    id: str
    source_type: str
    content: str
    associated_entity: str
    timestamp: int
    def __init__(self, *, id: str = ..., source_type: str = ..., content: str = ...,
                 associated_entity: str = ..., timestamp: int = ...) -> None: ...


class GraphFragment(Message):
    scenario_id: str
    generated_at: int
    transactions: Sequence[Transaction]
    nodes: Mapping[str, NodeAttributes]
    text_evidence: Sequence[TextEvidence]
    ground_truth_criminals: Sequence[str]
    def __init__(self, *, scenario_id: str = ..., generated_at: int = ...,
                 transactions: Sequence[Transaction] = ...,
                 nodes: Mapping[str, NodeAttributes] = ...,
                 text_evidence: Sequence[TextEvidence] = ...,
                 ground_truth_criminals: Sequence[str] = ...) -> None: ...


class InvestigationRequest(Message):
    subject_id: str
    alert_timestamp: int
    case_id: str
    hop_depth: int
    jurisdiction: str
    def __init__(self, *, subject_id: str = ..., alert_timestamp: int = ...,
                 case_id: str = ..., hop_depth: int = ...,
                 jurisdiction: str = ...) -> None: ...


class CitedEvidence(Message):
    transaction_id: str
    amount: float
    relevance: str
    timestamp: int
    def __init__(self, *, transaction_id: str = ..., amount: float = ...,
                 relevance: str = ..., timestamp: int = ...) -> None: ...


class InvestigationResult(Message):
    case_id: str
    sar_narrative: str
    typology_detected: str
    involved_entities: Sequence[str]
    cited_evidence: Sequence[CitedEvidence]
    confidence_score: float
    jurisdiction: str
    investigation_timestamp: int
    def __init__(self, *, case_id: str = ..., sar_narrative: str = ...,
                 typology_detected: str = ..., involved_entities: Sequence[str] = ...,
                 cited_evidence: Sequence[CitedEvidence] = ...,
                 confidence_score: float = ..., jurisdiction: str = ...,
                 investigation_timestamp: int = ...) -> None: ...


class LegacyTransaction(Message):
    transaction_id: str
    source: str
    target: str
    amount: float
    currency: str
    timestamp: str
    transaction_type: str
    memo: str
    label: str
    risk_score: float
    is_international: bool
    merchant_type: str


class KycProfile(Message):
    account_id: str
    entity_type: str
    name: str
    company: str
    address: str
    country: str
    swift_code: str
    iban: str
    risk_score: float
    verification_status: str
    created_at: str
    last_activity: str


class LegacyTransactionListResponse(Message):
    account_id: str
    transaction_count: int
    transactions: Sequence[LegacyTransaction]


class AccountConnection(Message):
    account_id: str
    relationship: str
    transaction_count: int
    total_amount: float


class AccountConnectionsResponse(Message):
    account_id: str
    connection_count: int
    connections: Sequence[AccountConnection]


class LegacyInvestigationAssessmentRequest(Message):
    participant_id: str
    investigation_data_json: str


class RubricBreakdown(Message):
    pattern_identification: float
    evidence_quality: float
    narrative_clarity: float
    completeness: float


class LegacyInvestigationAssessmentResponse(Message):
    score: float
    feedback: str
    rubric_breakdown: RubricBreakdown
    missed_indicators: Sequence[str]
    tool_call_count: int
    efficiency_score: float


class GraphNode(Message):
    id: str
    entity_type: str
    name: str
    country: str
    risk_score: float
    attributes: Mapping[str, str]


class GraphEdge(Message):
    source: str
    target: str
    amount: float
    label: str
    attributes: Mapping[str, str]


class FinancialGraph(Message):
    nodes: Sequence[GraphNode]
    edges: Sequence[GraphEdge]
    node_count: int
    edge_count: int


class EvidenceDocument(Message):
    document_id: str
    document_type: str
    subject_id: str
    date: str
    content: str
    metadata: Mapping[str, str]


class EvidenceListResponse(Message):
    document_count: int
    documents: Sequence[EvidenceDocument]
