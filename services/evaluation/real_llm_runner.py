"""Real-LLM Evaluation Runner measuring narrative faithfulness against verified evidence.

Compares faithfulness violation rate of real LLM providers (Groq / OpenAI) vs MockLLMProvider.
Operates deterministically offline when API keys are absent and reports provider status explicitly.
"""
import os
import json
import asyncio
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from domain.investigation.models import InvestigationRequest
from services.agent.llm_provider import (
    LLMProvider,
    MockLLMProvider,
    GroqLLMProvider,
    OpenAILLMProvider,
)
from services.evaluation.dataset import EvaluationDataset, GoldenTestCase
from services.agent.graph import GridLensInvestigationWorkflow
from services.config import INCIDENTS_FILE


class LLMFaithfulnessReport(BaseModel):
    provider_name: str
    model_name: str
    is_live_api: bool
    total_cases_evaluated: int
    faithful_cases: int
    unfaithful_cases: int
    faithfulness_rate_percent: float
    total_faithfulness_violations: int
    status: str = "completed"
    delta_vs_mock_percent: Optional[float]
    sample_violations: List[Dict[str, Any]] = Field(default_factory=list)


class RealLLMEvaluator:
    """Evaluates narrative faithfulness of LLM providers across the golden dataset."""

    @classmethod
    async def evaluate_provider(
        cls,
        provider: LLMProvider,
        provider_name: str,
        model_name: str,
        is_live: bool,
        test_cases: Optional[List[GoldenTestCase]] = None,
    ) -> LLMFaithfulnessReport:
        if test_cases is None:
            # Evaluate across curated cases
            test_cases = EvaluationDataset.get_all_test_cases()

        workflow = GridLensInvestigationWorkflow(llm_provider=provider)
        with INCIDENTS_FILE.open("r", encoding="utf-8") as f:
            incidents_seed = json.load(f)
        inc_map = {inc["incident_id"]: inc for inc in incidents_seed}

        total = len(test_cases)
        faithful_count = 0
        all_violations: List[Dict[str, Any]] = []

        for tc in test_cases:
            req = InvestigationRequest(
                investigation_id=f"REAL-EVAL-{tc.case_id}",
                incident_id=tc.target_incident_id,
                user_query=tc.query,
                target_equipment_id=tc.target_feeder_id,
            )
            inc_data = inc_map.get(tc.target_incident_id)
            res = await workflow.run_investigation(req, incident_data=inc_data)

            is_faithful = res.is_faithful
            violations = res.faithfulness_violations

            if is_faithful:
                faithful_count += 1
            else:
                all_violations.append({
                    "case_id": tc.case_id,
                    "query": tc.query,
                    "violations": violations,
                })

        faithfulness_rate = round((faithful_count / total) * 100.0, 1) if total else 0.0

        return LLMFaithfulnessReport(
            provider_name=provider_name,
            model_name=model_name,
            is_live_api=is_live,
            total_cases_evaluated=total,
            faithful_cases=faithful_count,
            unfaithful_cases=total - faithful_count,
            faithfulness_rate_percent=faithfulness_rate,
            total_faithfulness_violations=len(all_violations),
            delta_vs_mock_percent=None,
            sample_violations=all_violations[:5],
        )

    @classmethod
    async def run_comparative_evaluation(cls, allow_live: bool = False) -> Dict[str, Any]:
        """Executes Mock vs Configured Real LLM provider evaluation."""
        # 1. Run MockLLMProvider benchmark
        mock_provider = MockLLMProvider()
        mock_report = await cls.evaluate_provider(
            provider=mock_provider,
            provider_name="MockLLMProvider",
            model_name="deterministic-ledger-synthesis",
            is_live=False,
        )

        # 2. Check for configured live provider
        groq_key = os.getenv("GROQ_API_KEY", "")
        openai_key = os.getenv("OPENAI_API_KEY", "")

        if not allow_live or not (groq_key or openai_key):
            return {
                "mock_baseline": mock_report.model_dump(),
                "real_evaluation": {"status": "not_run", "reason": "Live evaluation requires explicit allow_live=True and credentials.",
                                    "is_live_api": False, "total_cases_evaluated": 0,
                                    "faithfulness_rate_percent": None, "provider_name": None, "model_name": None},
                "faithfulness_delta_percent": None,
            }
        if groq_key:
            real_provider = GroqLLMProvider(api_key=groq_key)
            p_name = "GroqLLMProvider"
            m_name = real_provider.model
            is_live = True
        elif openai_key:
            real_provider = OpenAILLMProvider(api_key=openai_key)
            p_name = "OpenAILLMProvider"
            m_name = real_provider.model
            is_live = True
        real_report = await cls.evaluate_provider(
            provider=real_provider,
            provider_name=p_name,
            model_name=m_name,
            is_live=is_live,
        )

        return {
            "mock_baseline": mock_report.model_dump(),
            "real_evaluation": real_report.model_dump(),
            "faithfulness_delta_percent": round(mock_report.faithfulness_rate_percent - real_report.faithfulness_rate_percent, 1),
        }


if __name__ == "__main__":
    async def main():
        print("\nExecuting Real-LLM Faithfulness Evaluation...")
        res = await RealLLMEvaluator.run_comparative_evaluation()
        print(json.dumps(res, indent=2))

    asyncio.run(main())
