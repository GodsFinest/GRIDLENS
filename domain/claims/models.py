"""Domain models for atomic verified Claims, strict FACT/INFERENCE/RECOMMENDATION typing, and conflict lifecycles."""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


from datetime import datetime, timezone
from typing import List, Optional, Dict, ClassVar


class ClaimType(str, Enum):
    FACT = "FACT"                      # Directly observable or deterministically derived from an authoritative source
    INFERENCE = "INFERENCE"            # Derived from verified facts using an explicit inference rule
    RECOMMENDATION = "RECOMMENDATION"  # Suggested next engineering or field investigation step


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"                      # Verified against authoritative source (for FACT)
    SUPPORTED_INFERENCE = "SUPPORTED_INFERENCE"  # Validated against verified premise claims and rules (for INFERENCE)
    UNVERIFIED = "UNVERIFIED"                  # Pending verification check
    REJECTED = "REJECTED"                      # Fact mismatch or unsupported premise; stripped from final claims
    CONFLICTED = "CONFLICTED"                  # Contradicts another verified fact; enters Conflict Lifecycle


class ConflictLifecycle(str, Enum):
    NO_CONFLICT = "NO_CONFLICT"
    CONFLICT_DETECTED = "CONFLICT_DETECTED"
    INVESTIGATION = "INVESTIGATION"
    CONFLICT_RESOLVED = "CONFLICT_RESOLVED"
    CONFLICT_UNRESOLVED = "CONFLICT_UNRESOLVED"


class ConflictTransition(BaseModel):
    from_state: ConflictLifecycle
    to_state: ConflictLifecycle
    rule_id: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)
    explanation: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ConflictTracker(BaseModel):
    current_state: ConflictLifecycle = ConflictLifecycle.NO_CONFLICT
    transitions: List[ConflictTransition] = Field(default_factory=list)

    LEGAL_TRANSITIONS: ClassVar[Dict[ConflictLifecycle, List[ConflictLifecycle]]] = {
        ConflictLifecycle.NO_CONFLICT: [ConflictLifecycle.CONFLICT_DETECTED],
        ConflictLifecycle.CONFLICT_DETECTED: [ConflictLifecycle.INVESTIGATION],
        ConflictLifecycle.INVESTIGATION: [ConflictLifecycle.CONFLICT_RESOLVED, ConflictLifecycle.CONFLICT_UNRESOLVED],
        ConflictLifecycle.CONFLICT_RESOLVED: [],
        ConflictLifecycle.CONFLICT_UNRESOLVED: [],
    }

    def advance_conflict(
        self,
        next_state: ConflictLifecycle,
        rule_id: Optional[str],
        evidence_ids: List[str],
        explanation: str,
    ) -> ConflictTransition:
        allowed = self.LEGAL_TRANSITIONS.get(self.current_state, [])
        if next_state not in allowed:
            raise ValueError(
                f"Illegal conflict state transition from {self.current_state} to {next_state}. "
                f"Allowed transitions: {allowed}"
            )
        transition = ConflictTransition(
            from_state=self.current_state,
            to_state=next_state,
            rule_id=rule_id,
            evidence_ids=evidence_ids,
            explanation=explanation,
        )
        self.transitions.append(transition)
        self.current_state = next_state
        return transition


class Claim(BaseModel):
    """Atomic claim unit comprising the verified engineering ledger."""
    claim_id: str
    statement: str
    claim_type: ClaimType
    evidence_ids: List[str] = Field(default_factory=list)
    premise_claim_ids: List[str] = Field(default_factory=list)  # Referenced for INFERENCE claims
    inference_rule_id: Optional[str] = None                    # Rule ID defining how inference derives from premises
    inference_result: Optional[dict] = None  # Recomputed conclusion, never trusted on its own
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    verification_source: Optional[str] = None                  # e.g., "COMTRADE_ANALYZER", "IN_MEMORY_TOPOLOGY", "CONFIG_VALIDATOR"
    conflict_lifecycle: ConflictLifecycle = ConflictLifecycle.NO_CONFLICT
    conflict_transitions: List[ConflictTransition] = Field(default_factory=list)
    verification_notes: Optional[str] = None

    def advance_conflict(
        self,
        next_state: ConflictLifecycle,
        rule_id: Optional[str],
        evidence_ids: List[str],
        explanation: str,
    ) -> ConflictTransition:
        tracker = ConflictTracker(current_state=self.conflict_lifecycle, transitions=self.conflict_transitions)
        transition = tracker.advance_conflict(next_state, rule_id, evidence_ids, explanation)
        self.conflict_lifecycle = tracker.current_state
        self.conflict_transitions = tracker.transitions
        return transition
