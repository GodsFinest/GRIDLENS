"""Offline must not masquerade as a live model experiment."""
import pytest
from services.evaluation.real_llm_runner import RealLLMEvaluator


@pytest.mark.asyncio
async def test_real_llm_requires_explicit_live_opt_in(monkeypatch):
    # Even credentials in the environment must not trigger paid calls by default.
    monkeypatch.setenv("GROQ_API_KEY", "not-a-real-key")
    res = await RealLLMEvaluator.run_comparative_evaluation()
    assert res["mock_baseline"]["faithfulness_rate_percent"] == 100.0
    assert res["real_evaluation"]["status"] == "not_run"
    assert res["real_evaluation"]["total_cases_evaluated"] == 0
    assert res["real_evaluation"]["faithfulness_rate_percent"] is None
    assert res["faithfulness_delta_percent"] is None
