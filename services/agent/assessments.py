"""EvidenceAssessor evaluating relationships between Evidence objects and Candidate Hypotheses."""
from typing import List
from domain.evidence.models import Evidence, EvidenceKind
from domain.evidence.assessment import EvidenceAssessment, AssessmentRelationship


class EvidenceAssessor:
    """Evaluates contextual support and contradiction between atomic Evidence and Hypotheses."""

    @classmethod
    def assess_evidence_for_hypotheses(cls, evidence_list: List[Evidence]) -> List[EvidenceAssessment]:
        assessments: List[EvidenceAssessment] = []
        ast_counter = 1

        for ev in evidence_list:
            # Check for COMTRADE overcurrent evidence
            if ev.kind == EvidenceKind.OVERCURRENT_EXCEEDED and ev.structured_value is True:
                assessments.append(EvidenceAssessment(
                    assessment_id=f"AST_{ast_counter:03d}",
                    evidence_id=ev.evidence_id,
                    hypothesis_id="H1",
                    relationship=AssessmentRelationship.SUPPORTS,
                    weight=3.0,
                    rule_id="RULE_ASSESS_OVERCURRENT_GENUINE_FAULT",
                    explanation="Measured fault current exceeds pickup threshold, strongly supporting genuine overcurrent trip on H1.",
                ))
                ast_counter += 1

            # Check for COMTRADE truncation
            if ev.kind == EvidenceKind.RECORDING_TRUNCATED and ev.structured_value is True:
                assessments.append(EvidenceAssessment(
                    assessment_id=f"AST_{ast_counter:03d}",
                    evidence_id=ev.evidence_id,
                    hypothesis_id="H6",
                    relationship=AssessmentRelationship.SUPPORTS,
                    weight=5.0,
                    rule_id="RULE_ASSESS_TRUNCATION_INSUFFICIENT",
                    explanation="Waveform was truncated before clearing, supporting H6 (Insufficient Evidence).",
                ))
                ast_counter += 1
                assessments.append(EvidenceAssessment(
                    assessment_id=f"AST_{ast_counter:03d}",
                    evidence_id=ev.evidence_id,
                    hypothesis_id="H1",
                    relationship=AssessmentRelationship.CONTRADICTS,
                    weight=-4.0,
                    rule_id="RULE_ASSESS_TRUNCATION_BLOCKS_H1",
                    explanation="Cannot substantiate genuine fault without complete clearance oscillography.",
                ))
                ast_counter += 1

            # Check for configuration validation violations (Phase Inversion)
            if ev.kind == EvidenceKind.PHASE_INVERSION_VIOLATION:
                assessments.append(EvidenceAssessment(
                    assessment_id=f"AST_{ast_counter:03d}",
                    evidence_id=ev.evidence_id,
                    hypothesis_id="H3",
                    relationship=AssessmentRelationship.SUPPORTS,
                    weight=5.0,
                    rule_id="RULE-CONFLICT-002",
                    explanation="Validation detected CT Phase inversion, confirming H3 (Secondary Wiring / Channel Mapping Error).",
                ))
                ast_counter += 1
                assessments.append(EvidenceAssessment(
                    assessment_id=f"AST_{ast_counter:03d}",
                    evidence_id=ev.evidence_id,
                    hypothesis_id="H1",
                    relationship=AssessmentRelationship.CONTRADICTS,
                    weight=-4.5,
                    rule_id="RULE-CONFLICT-001",
                    explanation="Relay reported phase conflicts with physical waveform channel due to inverted CT mapping.",
                ))
                ast_counter += 1

            # Check for configuration passed
            if ev.kind == EvidenceKind.CONFIG_PASSED and ev.structured_value is True:
                assessments.append(EvidenceAssessment(
                    assessment_id=f"AST_{ast_counter:03d}",
                    evidence_id=ev.evidence_id,
                    hypothesis_id="H1",
                    relationship=AssessmentRelationship.SUPPORTS,
                    weight=1.5,
                    rule_id="RULE_ASSESS_CONFIG_PASSED_H1",
                    explanation="Substation configuration is structurally valid with 0 violations.",
                ))
                ast_counter += 1
                assessments.append(EvidenceAssessment(
                    assessment_id=f"AST_{ast_counter:03d}",
                    evidence_id=ev.evidence_id,
                    hypothesis_id="H3",
                    relationship=AssessmentRelationship.CONTRADICTS,
                    weight=-3.0,
                    rule_id="RULE_ASSESS_CONFIG_PASSED_REFUTES_H3",
                    explanation="Configuration validation passed, refuting channel mapping errors.",
                ))
                ast_counter += 1

            # Check for valid breaker clearing time
            if ev.kind == EvidenceKind.CLEARING_TIME:
                clearing_ms = float(ev.structured_value)
                if clearing_ms <= 75.0:
                    assessments.append(EvidenceAssessment(
                        assessment_id=f"AST_{ast_counter:03d}",
                        evidence_id=ev.evidence_id,
                        hypothesis_id="H4",
                        relationship=AssessmentRelationship.CONTRADICTS,
                        weight=-3.0,
                        rule_id="RULE_ASSESS_NORMAL_CLEARING_REFUTES_H4",
                        explanation=f"Breaker cleared fault in {clearing_ms} ms (normal speed), refuting breaker mechanical failure (H4).",
                    ))
                    ast_counter += 1

        # Check for breaker trip without overcurrent (Settings Misoperation H2)
        has_breaker_clearing = any(
            ev.kind == EvidenceKind.CLEARING_TIME
            or (ev.kind == EvidenceKind.SOE_EVENT and any(w in ev.fact.lower() for w in ["trip", "open", "cleared"]))
            for ev in evidence_list
        )
        has_overcurrent = any(
            ev.kind == EvidenceKind.OVERCURRENT_EXCEEDED and ev.structured_value is True
            for ev in evidence_list
        )
        has_inversion = any(
            ev.kind == EvidenceKind.PHASE_INVERSION_VIOLATION
            for ev in evidence_list
        )
        has_truncation = any(
            ev.kind == EvidenceKind.RECORDING_TRUNCATED and ev.structured_value is True
            for ev in evidence_list
        )

        if has_breaker_clearing and not has_overcurrent and not has_inversion and not has_truncation:
            clearing_ev = next(
                (ev for ev in evidence_list if ev.kind == EvidenceKind.CLEARING_TIME),
                evidence_list[0] if evidence_list else None
            )
            ev_id = clearing_ev.evidence_id if clearing_ev else "EV_ASSESS"
            assessments.append(EvidenceAssessment(
                assessment_id=f"AST_{ast_counter:03d}",
                evidence_id=ev_id,
                hypothesis_id="H2",
                relationship=AssessmentRelationship.SUPPORTS,
                weight=4.0,
                rule_id="RULE_ASSESS_NO_PICKUP_SUPPORTS_H2",
                explanation="Breaker operation occurred without overcurrent threshold exceedance or channel inversion, supporting Relay Settings Misoperation (H2).",
            ))
            ast_counter += 1
            assessments.append(EvidenceAssessment(
                assessment_id=f"AST_{ast_counter:03d}",
                evidence_id=ev_id,
                hypothesis_id="H1",
                relationship=AssessmentRelationship.CONTRADICTS,
                weight=-3.0,
                rule_id="RULE_ASSESS_NO_PICKUP_CONTRADICTS_H1",
                explanation="Absence of overcurrent threshold exceedance contradicts genuine primary fault (H1).",
            ))
            ast_counter += 1

        return assessments
