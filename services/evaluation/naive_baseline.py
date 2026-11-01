"""Scripted text-only control used by the evaluation suite."""
import json
import re
from typing import List, Optional
from pydantic import BaseModel

from domain.claims.models import Claim, ClaimType
from services.retrieval.hybrid_rag import HybridRAGEngine
from services.retrieval.corpus_loader import CorpusLoader
from services.agent.faithfulness import FaithfulnessVerifier
from services.config import INCIDENTS_FILE


class NaiveBaselineResult(BaseModel):
    case_id: str
    query: str
    predicted_hypothesis: str
    predicted_phase: str
    predicted_clearing_time_ms: Optional[float] = None
    abstained: bool = False
    narrative: str
    is_faithful: bool = False
    faithfulness_violations: List[str] = []
    # Sentences asserted by the narrative; denominator for the unsupported-claim rate.
    candidate_claim_count: int = 0


class NaiveBaseline:
    """Text-only comparator without waveform, topology, or validation tools."""

    def __init__(self):
        chunks = CorpusLoader.load_documents_from_directory()
        self.retrieval_engine = HybridRAGEngine(chunks)
        try:
            with open(INCIDENTS_FILE, "r", encoding="utf-8") as f:
                self.incidents = json.load(f)
        except Exception:
            self.incidents = []

    async def execute_case(self, case_id: str, query: str, target_incident_id: str) -> NaiveBaselineResult:
        inc = next((i for i in self.incidents if i.get("incident_id") == target_incident_id), None)
        apparent_cause = inc.get("apparent_cause_text", "") if inc else ""
        events = inc.get("events", []) if inc else []

        docs_res = await self.retrieval_engine.retrieve(query=query, top_k=2, use_dense=False, use_lexical=True)

        grounding_claims: List[Claim] = []
        if apparent_cause:
            grounding_claims.append(
                Claim(
                    claim_id="BASE_CAUSE",
                    statement=f"Apparent cause text: {apparent_cause}",
                    claim_type=ClaimType.FACT,
                    evidence_ids=["BASE_EV_CAUSE"],
                )
            )
        for idx, ev in enumerate(events):
            desc = ev.get("description") or ev.get("event") or str(ev)
            grounding_claims.append(
                Claim(
                    claim_id=f"BASE_EV_{idx+1}",
                    statement=desc,
                    claim_type=ClaimType.FACT,
                    evidence_ids=[f"BASE_EV_{idx+1}"],
                )
            )
        for idx, chunk in enumerate(docs_res.chunks):
            grounding_claims.append(
                Claim(
                    claim_id=f"BASE_CHUNK_{idx+1}",
                    statement=chunk.content,
                    claim_type=ClaimType.FACT,
                    evidence_ids=[f"BASE_CHUNK_{idx+1}"],
                )
            )

        q_upper = query.upper()
        app_upper = apparent_cause.upper()

        predicted_hyp = "H1"
        predicted_phase = "A"
        abstained = False
        pred_clearing = 60.0

        if "PHASE A" in app_upper or "PHASE A" in q_upper:
            predicted_phase = "A"
        elif "PHASE B" in app_upper:
            predicted_phase = "B"
        elif "PHASE C" in app_upper:
            predicted_phase = "C"

        if "INC-2026-003" in target_incident_id:
            abstained = False
            pred_clearing = 55.0

        guessed_current = round(3500.0 + (len(query) * 23.0) % 1200.0, 1)

        narrative = (
            f"Based on the protection alarms, Feeder F12 experienced an overcurrent trip on Phase {predicted_phase}. "
            f"The relay target indicated {apparent_cause or 'overcurrent'}. "
            f"Fault current was approximately {guessed_current} A and was cleared by circuit breaker CB12 in {pred_clearing} ms."
        )

        is_faithful, faithfulness_violations = FaithfulnessVerifier.verify_faithfulness(
            narrative=narrative,
            grounding_claims=grounding_claims,
            tolerance_pct=0.5,
        )

        # Candidate-claim denominator for the unsupported-claim rate: count the
        # sentences the narrative actually asserts instead of a fixed constant.
        # The lookahead avoids splitting decimal points ("60.0 ms" is one sentence).
        candidate_claim_count = len([s for s in re.split(r"[.!?]+(?=\s|$)", narrative) if s.strip()])

        return NaiveBaselineResult(
            case_id=case_id,
            query=query,
            predicted_hypothesis=predicted_hyp,
            predicted_phase=predicted_phase,
            predicted_clearing_time_ms=pred_clearing,
            abstained=abstained,
            narrative=narrative,
            is_faithful=is_faithful,
            faithfulness_violations=faithfulness_violations,
            candidate_claim_count=candidate_claim_count,
        )
