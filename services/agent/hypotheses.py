"""Hypothesis evaluation and scoring engine based on explicit EvidenceAssessments."""
from typing import List, Dict
from domain.evidence.models import Evidence, EvidenceKind
from domain.evidence.assessment import EvidenceAssessment, AssessmentRelationship
from domain.hypotheses.models import Hypothesis, HypothesisSufficiencyStatus


class HypothesisEngine:
    """Instantiates candidate hypotheses and calculates deterministic evidence scores."""

    @classmethod
    def create_candidate_hypotheses(cls) -> Dict[str, Hypothesis]:
        return {
            "H1": Hypothesis(
                hypothesis_id="H1",
                code="H1",
                title="Genuine Primary Feeder Fault",
                description="Feeder experienced a physical phase-to-ground or phase-to-phase overcurrent fault correctly cleared by primary protection.",
            ),
            "H2": Hypothesis(
                hypothesis_id="H2",
                code="H2",
                title="Protection Setting Misoperation",
                description="Relay pickup current threshold or time dial curve was misconfigured, causing premature or uncoordinated tripping.",
            ),
            "H3": Hypothesis(
                hypothesis_id="H3",
                code="H3",
                title="Secondary CT Wiring / Channel Mapping Inconsistency",
                description="Secondary CT leads or IED analog channel configuration mappings were transposed, causing misleading phase reporting.",
            ),
            "H4": Hypothesis(
                hypothesis_id="H4",
                code="H4",
                title="Breaker Mechanical / Trip Circuit Failure",
                description="Circuit breaker mechanism failed to open or exhibited severe contact parting delay exceeding rating.",
            ),
            "H5": Hypothesis(
                hypothesis_id="H5",
                code="H5",
                title="Communication / SOE Desynchronization",
                description="Relay SOE timestamps were desynchronized from GPS master, generating false sequential ordering.",
            ),
            "H6": Hypothesis(
                hypothesis_id="H6",
                code="H6",
                title="Insufficient Evidence to Determine Root Cause",
                description="Waveform data was truncated, secondary CT ratios were missing, or required engineering records were unavailable.",
            ),
        }

    @classmethod
    def evaluate_hypotheses(
        cls,
        evidence_list: List[Evidence],
        assessments: List[EvidenceAssessment],
    ) -> List[Hypothesis]:
        candidates = cls.create_candidate_hypotheses()

        # Group assessments by hypothesis
        for ast in assessments:
            if ast.hypothesis_id in candidates:
                hyp = candidates[ast.hypothesis_id]
                if ast.relationship == AssessmentRelationship.SUPPORTS:
                    hyp.supporting_assessments.append(ast)
                    hyp.deterministic_score += ast.weight
                elif ast.relationship == AssessmentRelationship.CONTRADICTS:
                    hyp.contradicting_assessments.append(ast)
                    hyp.deterministic_score += ast.weight  # Negative weight reduces score

        # Check for missing evidence notes
        has_truncation = any(ev.kind == EvidenceKind.RECORDING_TRUNCATED and ev.structured_value is True for ev in evidence_list)
        has_ct_ratio_missing = any(ev.kind == EvidenceKind.CONFIG_VIOLATION and ev.structured_value == "RULE-CFG-004" for ev in evidence_list)

        if has_truncation:
            candidates["H1"].missing_evidence_descriptions.append("Complete post-fault clearance COMTRADE oscillography waveform.")
            candidates["H2"].missing_evidence_descriptions.append("Complete waveform duration to verify time-overcurrent curve integration.")
            candidates["H6"].deterministic_score += 4.0

        if has_ct_ratio_missing:
            candidates["H1"].missing_evidence_descriptions.append("Calibrated CT primary/secondary ratio setting.")
            candidates["H6"].deterministic_score += 3.0

        # Sort hypotheses by deterministic score descending
        sorted_hyps = sorted(candidates.values(), key=lambda h: h.deterministic_score, reverse=True)

        # Calculate normalized confidence (Softmax or proportional bounded between 0.05 and 0.98)
        max_score = sorted_hyps[0].deterministic_score if sorted_hyps else 0.0
        for hyp in sorted_hyps:
            if hyp.deterministic_score <= 0.0:
                hyp.confidence_normalized = 0.05
                hyp.sufficiency_status = HypothesisSufficiencyStatus.CONTRADICTED if hyp.contradicting_assessments else HypothesisSufficiencyStatus.INSUFFICIENT
            else:
                # Proportional confidence calculation
                hyp.confidence_normalized = round(min(0.96, max(0.10, hyp.deterministic_score / max(max_score + 1.0, 1.0))), 2)
                hyp.sufficiency_status = HypothesisSufficiencyStatus.SUFFICIENT

        # Mark top hypothesis as primary diagnosis
        if sorted_hyps:
            sorted_hyps[0].is_primary_diagnosis = True

        return sorted_hyps
