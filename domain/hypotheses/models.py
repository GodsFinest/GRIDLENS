"""Domain model for candidate engineering hypotheses and their evaluated evidence scores."""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from domain.evidence.assessment import EvidenceAssessment


class HypothesisSufficiencyStatus(str, Enum):
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"
    CONTRADICTED = "CONTRADICTED"
    UNKNOWN = "UNKNOWN"


class Hypothesis(BaseModel):
    """Structured candidate hypothesis evaluated via explicit EvidenceAssessments."""
    hypothesis_id: str
    code: str  # e.g., "H1", "H2", "H3", "H4", "H5", "H6"
    title: str
    description: str
    supporting_assessments: List[EvidenceAssessment] = Field(default_factory=list)
    contradicting_assessments: List[EvidenceAssessment] = Field(default_factory=list)
    missing_evidence_descriptions: List[str] = Field(default_factory=list)
    deterministic_score: float = 0.0
    confidence_normalized: float = 0.0  # 0.0 to 1.0 based on normalized weight
    sufficiency_status: HypothesisSufficiencyStatus = HypothesisSufficiencyStatus.UNKNOWN
    is_primary_diagnosis: bool = False
