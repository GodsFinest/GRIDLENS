"""Domain models for investigation requests, stateful investigation results, sufficiency policies, and audit traces."""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from domain.claims.models import Claim, ConflictLifecycle, ConflictTransition
from domain.hypotheses.models import Hypothesis
from domain.models.results import RetrievedDocumentChunk


class InvestigationType(str, Enum):
    PROTECTION_EVENT_INVESTIGATION = "PROTECTION_EVENT_INVESTIGATION"  # Full multi-source event investigation
    TOPOLOGY_INQUIRY = "TOPOLOGY_INQUIRY"                            # "Which relay protects F12?" -> Graph only
    DOCUMENTATION_QA = "DOCUMENTATION_QA"                            # "What does ANSI 51 mean?" -> RAG only
    CONFIGURATION_VALIDATION = "CONFIGURATION_VALIDATION"            # "Is F12 configuration valid?" -> Graph + Validator
    EVENT_TIMELINE_RECONCILIATION = "EVENT_TIMELINE_RECONCILIATION"  # "Show F12 sequence of events" -> SOE engine only


class EvidenceRequirementPolicy(BaseModel):
    """Context-aware evidence requirement policy defining what evidence is needed to consider an investigation sufficient."""
    investigation_type: InvestigationType
    required_source_types: List[str] = Field(default_factory=list)      # e.g., ["GRAPH", "COMTRADE", "EVENT_LOG"]
    preferred_source_types: List[str] = Field(default_factory=list)     # e.g., ["DOCUMENT", "INCIDENT_HISTORY"]
    must_resolve_contradictions: bool = True
    min_verified_facts: int = 1


class AuditTraceEntry(BaseModel):
    step_index: int
    timestamp: str
    stage: str  # e.g., "INTENT_CLASSIFICATION", "TOOL_EXECUTION", "EVIDENCE_CONSTRUCTION", "HYPOTHESIS_EVALUATION", "CLAIM_VERIFICATION", "PROSE_SYNTHESIS"
    tool_invoked: Optional[str] = None
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs_summary: str = ""
    duration_ms: float = 0.0


class InvestigationRequest(BaseModel):
    investigation_id: Optional[str] = None
    incident_id: Optional[str] = None
    user_query: str = Field(..., min_length=3, max_length=2000)
    user_role: str = "ENGINEER"  # "VIEWER", "ENGINEER", "APPROVER"
    target_equipment_id: Optional[str] = None


class InvestigationResult(BaseModel):
    """The canonical structured investigation output strictly generated from verified claims and supported inferences."""
    investigation_id: str
    incident_id: Optional[str] = None
    investigation_type: InvestigationType
    user_query: str
    diagnosis_title: str
    diagnosis_summary: str
    confidence_score: float = 0.0  # 0.0 to 1.0 derived from evidence score
    confidence_interpretation: str = "Heuristic evidence-ranking score, not a calibrated probability or confirmed root cause."
    is_sufficient: bool = True
    sufficiency_reason: str = ""
    conflict_lifecycle: ConflictLifecycle = ConflictLifecycle.NO_CONFLICT
    conflict_explanation: Optional[str] = None
    conflict_transitions: List[ConflictTransition] = Field(default_factory=list)

    hypotheses: List[Hypothesis] = Field(default_factory=list)
    verified_facts: List[Claim] = Field(default_factory=list)
    supported_inferences: List[Claim] = Field(default_factory=list)
    rejected_claims: List[Claim] = Field(default_factory=list)
    unresolved_contradictions: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    recommendations: List[Claim] = Field(default_factory=list)
    citations: List[RetrievedDocumentChunk] = Field(default_factory=list)

    is_faithful: bool = True
    faithfulness_violations: List[str] = Field(default_factory=list)

    execution_trace: List[AuditTraceEntry] = Field(default_factory=list)
    created_at: str
    duration_ms: float = 0.0
