"""Domain model for contextual Evidence Assessment mapping Evidence to Candidate Hypotheses."""
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class AssessmentRelationship(str, Enum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    NEUTRAL = "NEUTRAL"
    PREREQUISITE = "PREREQUISITE"


class EvidenceAssessment(BaseModel):
    """Contextual assessment linking an atomic Evidence fact to a specific Hypothesis."""
    assessment_id: str
    evidence_id: str
    hypothesis_id: str
    relationship: AssessmentRelationship
    weight: float  # e.g., +2.0 for strong support, -3.0 for fatal contradiction
    rule_id: str  # e.g., "OVERCURRENT_THRESHOLD_SUPPORT_01", "CHANNEL_MAPPING_CONTRADICTION_02"
    explanation: str  # Human-readable engineering rationale for the assessment
