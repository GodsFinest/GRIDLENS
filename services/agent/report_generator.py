from typing import List, Optional, Any
from domain.claims.models import Claim, ClaimType, ConflictLifecycle
from domain.hypotheses.models import Hypothesis
from domain.investigation.models import (
    InvestigationResult,
    InvestigationType,
    AuditTraceEntry,
)
from domain.models.results import RetrievedDocumentChunk
from services.agent.llm_provider import LLMProvider, get_configured_llm_provider


class ReportGenerator:
    """Synthesizes final investigation report exclusively from verified claims and supported inferences."""

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.llm_provider = llm_provider or get_configured_llm_provider()

    async def generate_final_report(
        self,
        investigation_id: str,
        incident_id: Optional[str],
        investigation_type: InvestigationType,
        user_query: str,
        hypotheses: List[Hypothesis],
        verified_facts: List[Claim],
        supported_inferences: List[Claim],
        rejected_claims: List[Claim],
        is_sufficient: bool,
        sufficiency_reason: str,
        conflict_lifecycle: ConflictLifecycle,
        citations: List[RetrievedDocumentChunk],
        execution_trace: List[AuditTraceEntry],
        start_time_iso: str,
        duration_ms: float,
        conflict_transitions: Optional[List[Any]] = None,
        conflict_explanation: Optional[str] = None,
    ) -> InvestigationResult:
        top_hyp = hypotheses[0] if hypotheses else None

        # Determine diagnosis title
        if investigation_type == InvestigationType.DOCUMENTATION_QA:
            diagnosis_title = "TECHNICAL DOCUMENTATION INQUIRY ANSWERED"
            confidence_score = 1.0
        elif investigation_type == InvestigationType.TOPOLOGY_INQUIRY:
            diagnosis_title = "SUBSTATION TOPOLOGY INQUIRY CONCLUDED"
            confidence_score = 1.0
        elif investigation_type == InvestigationType.CONFIGURATION_VALIDATION:
            diagnosis_title = "BAY CONFIGURATION VALIDATION COMPLETED"
            confidence_score = 1.0
        elif not is_sufficient or (top_hyp and top_hyp.code == "H6"):
            diagnosis_title = "INSUFFICIENT EVIDENCE TO DETERMINE ROOT CAUSE"
            confidence_score = 0.15
        elif top_hyp and top_hyp.code == "H3":
            diagnosis_title = "SECONDARY CT CHANNEL MAPPING INCONSISTENCY (RESOLVED)"
            confidence_score = top_hyp.confidence_normalized
        elif top_hyp and top_hyp.code == "H1":
            diagnosis_title = "MEASURED OVERCURRENT — ROOT CAUSE REQUIRES ENGINEERING REVIEW"
            confidence_score = top_hyp.confidence_normalized
        else:
            diagnosis_title = f"LEADING HYPOTHESIS — {top_hyp.title}" if top_hyp else "INVESTIGATION CONCLUDED"
            confidence_score = top_hyp.confidence_normalized if top_hyp else 0.5

        recs = [c for c in verified_facts if c.claim_type == ClaimType.RECOMMENDATION]

        # 1. Deterministic Fallback Template
        fact_lines = [f"- {c.statement}" for c in verified_facts if c.claim_type == ClaimType.FACT]
        inference_lines = [f"- {c.statement}" for c in supported_inferences]
        recommendation_lines = [f"- {c.statement}" for c in recs]
        sections = [f"GridLens Investigation Finding: {diagnosis_title}."]
        if not is_sufficient:
            sections.append(f"Sufficiency: {sufficiency_reason}")
        if fact_lines:
            sections.append("Verified facts:\n" + "\n".join(fact_lines))
        if inference_lines:
            sections.append("Supported inferences:\n" + "\n".join(inference_lines))
        if recommendation_lines:
            sections.append("Recommendations:\n" + "\n".join(recommendation_lines))
        deterministic_narrative = "\n\n".join(sections)

        # 2. Build Grounding Envelope for LLM
        system_prompt = (
            "You are GridLens, an expert substation protection engineer report assistant. "
            "Select and order complete verbatim statements from the supplied ledger. "
            "Do not paraphrase, combine clauses, or add a diagnosis. Use only the headings VERIFIED FACTS:, SUPPORTED INFERENCES:, RECOMMENDATIONS:. "
            "You may NOT introduce any numerical value, entity name, equipment identifier, timestamp, "
            "or causal statement that is not present in the verified facts above. "
            "Any statement not supported by the facts is a strict violation."
        )
        prompt_lines = [
            f"TOP HYPOTHESIS: {diagnosis_title}",
            "\nVERIFIED FACTS:",
        ]
        for c in verified_facts:
            if c.claim_type == ClaimType.FACT:
                prompt_lines.append(f"- {c.statement}")
        if supported_inferences:
            prompt_lines.append("\nSUPPORTED INFERENCES:")
            for c in supported_inferences:
                prompt_lines.append(f"- {c.statement}")
        if recs:
            prompt_lines.append("\nRECOMMENDATIONS:")
            for c in recs:
                prompt_lines.append(f"- {c.statement}")

        user_prompt = "\n".join(prompt_lines)

        # 3. Generate candidate LLM prose narrative
        is_faithful = True
        faithfulness_violations: List[str] = []
        final_prose = deterministic_narrative

        try:
            from services.agent.faithfulness import FaithfulnessVerifier
            candidate_prose = await self.llm_provider.generate_response(system_prompt, user_prompt)
            if candidate_prose and candidate_prose.strip():
                is_faithful, violations = FaithfulnessVerifier.verify_faithfulness(
                    narrative=candidate_prose,
                    grounding_claims=verified_facts + supported_inferences,
                    tolerance_pct=0.5,
                )
                if is_faithful:
                    final_prose = candidate_prose.strip()
                else:
                    faithfulness_violations = violations
                    final_prose = deterministic_narrative
        except Exception as exc:
            is_faithful = False
            faithfulness_violations = [f"Narrative provider unavailable ({type(exc).__name__}); deterministic report used."]
            final_prose = deterministic_narrative

        unresolved_contradictions = []
        if conflict_lifecycle == ConflictLifecycle.CONFLICT_UNRESOLVED:
            unresolved_contradictions.append(conflict_explanation or "Cross-source observations remain inconsistent; see the cited conflict transitions.")

        missing_evidence = []
        if not is_sufficient:
            missing_evidence.append(sufficiency_reason)

        return InvestigationResult(
            investigation_id=investigation_id,
            incident_id=incident_id,
            investigation_type=investigation_type,
            user_query=user_query,
            diagnosis_title=diagnosis_title,
            diagnosis_summary=final_prose,
            confidence_score=confidence_score,
            is_sufficient=is_sufficient,
            sufficiency_reason=sufficiency_reason,
            conflict_lifecycle=conflict_lifecycle,
            conflict_explanation=conflict_explanation,
            conflict_transitions=conflict_transitions or [],
            hypotheses=hypotheses,
            verified_facts=[c for c in verified_facts if c.claim_type == ClaimType.FACT],
            supported_inferences=supported_inferences,
            rejected_claims=rejected_claims,
            unresolved_contradictions=unresolved_contradictions,
            missing_evidence=missing_evidence,
            recommendations=recs,
            citations=citations,
            is_faithful=is_faithful,
            faithfulness_violations=faithfulness_violations,
            execution_trace=execution_trace,
            created_at=start_time_iso,
            duration_ms=round(duration_ms, 2),
        )
