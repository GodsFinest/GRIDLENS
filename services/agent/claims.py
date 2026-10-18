"""Construct source quotations and executable, measurement-bound inferences."""
from domain.evidence.models import EvidenceKind as K
from domain.claims.models import Claim, ClaimType, ConflictLifecycle
from services.agent.inference_rules import derive, render, OVERCURRENT, INCOMPLETE, RECOMMENDATIONS


class ClaimConstructor:
    @classmethod
    def construct_candidate_claims(cls, evidence_list, hypotheses,
                                   conflict_lifecycle=ConflictLifecycle.NO_CONFLICT):
        claims = [Claim(claim_id=f"C{i:02d}", statement=ev.fact, claim_type=ClaimType.FACT,
                        evidence_ids=[ev.evidence_id], verification_source=ev.tool_name,
                        conflict_lifecycle=conflict_lifecycle)
                  for i, ev in enumerate(evidence_list, 1)]
        fact_ids = {c.evidence_ids[0]: c.claim_id for c in claims}
        candidates = []
        for ev in evidence_list:
            if ev.kind == K.RECORDING_TRUNCATED:
                candidates.append((INCOMPLETE, [ev]))
            elif ev.kind == K.OVERCURRENT_EXCEEDED:
                for current in evidence_list:
                    if current.kind == K.CHANNEL_RMS:
                        candidates.append((OVERCURRENT, [ev, current]))
        for rule, premises in candidates:
            result = derive(rule, premises)
            if result is None:
                continue
            claims.append(Claim(claim_id=f"C{len(claims)+1:02d}", statement=render(rule, result),
                                claim_type=ClaimType.INFERENCE, evidence_ids=[e.evidence_id for e in premises],
                                premise_claim_ids=[fact_ids[e.evidence_id] for e in premises],
                                inference_rule_id=rule, inference_result=result,
                                verification_source="EXECUTABLE_RULE", conflict_lifecycle=conflict_lifecycle))
        recommendations = [RECOMMENDATIONS[0]]
        if any(e.kind == K.RECORDING_TRUNCATED for e in evidence_list):
            recommendations.append(RECOMMENDATIONS[1])
        if any(e.kind == K.PHASE_INVERSION_VIOLATION for e in evidence_list):
            recommendations.append(RECOMMENDATIONS[2])
        for statement in recommendations:
            claims.append(Claim(claim_id=f"C{len(claims)+1:02d}", statement=statement,
                                claim_type=ClaimType.RECOMMENDATION, verification_source="REVIEW_GUIDANCE",
                                conflict_lifecycle=conflict_lifecycle))
        return claims
