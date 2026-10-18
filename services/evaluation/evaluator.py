"""Evaluation benchmark runner executing Baseline vs Full GridLens vs dynamic Ablation suite."""
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from domain.investigation.models import InvestigationRequest
from domain.models.results import (
    TopologyQueryResult,
    ComtradeAnalysisResult,
    ValidationResult,
    HistoricalIncidentResult,
    DocumentRetrievalResult,
)
from services.evaluation.dataset import EvaluationDataset, GoldenTestCase
from services.agent.graph import GridLensInvestigationWorkflow
from services.tools.topology_tool import TopologyTool
from services.tools.waveform_tool import WaveformTool
from services.tools.validation_tool import ValidationTool
from services.tools.history_tool import HistoryTool
from services.tools.retrieval_tool import RetrievalTool
from services.config import INCIDENTS_FILE

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


class EvaluationMetrics(BaseModel):
    total_test_cases: int = 0
    passed_cases: int = 0
    accuracy_percent: float = 0.0
    diagnosis_accuracy_percent: float = 0.0
    physical_accuracy_percent: Optional[float] = None
    tool_selection_accuracy_percent: float = 0.0
    abstention_accuracy_percent: float = 0.0
    false_abstention_percent: float = 0.0
    contradiction_detection_percent: float = 0.0
    unsupported_claim_rate_percent: float = 0.0
    avg_latency_ms: float = 0.0
    latency_p95_ms: float = 0.0


class EvaluationRunReport(BaseModel):
    system_name: str
    metrics: EvaluationMetrics
    detailed_results: List[Dict[str, Any]] = Field(default_factory=list)


# --- Ablation Tool Wrappers for Systematic Sensitivity Testing ---

class DisabledTopologyTool(TopologyTool):
    async def execute(self, feeder_id: str = "F12", equipment_id: Optional[str] = None) -> TopologyQueryResult:
        return TopologyQueryResult(
            feeder_id=feeder_id,
            bay_id="UNKNOWN_BAY",
            connected_bus_id="UNKNOWN_BUS",
            primary_relay_id="UNKNOWN_RELAY",
            controlled_breaker_id="UNKNOWN_BREAKER",
            ied_id="UNKNOWN_IED",
            is_topology_complete=False,
            metadata={"ablation": "Topology tool disabled"},
        )


class DisabledWaveformTool(WaveformTool):
    async def execute(self, incident_id: str = "INC-2026-001", pickup_threshold_a: float = 2500.0) -> ComtradeAnalysisResult:
        return ComtradeAnalysisResult(
            incident_id=incident_id,
            sample_rate_hz=0.0,
            total_samples=0,
            duration_ms=0.0,
            is_truncated=True,
            analysis_notes=["Ablation: Waveform tool disabled."],
        )


class DisabledValidationTool(ValidationTool):
    async def execute(self, bay_id: str = "BAY_F12", feeder_id: Optional[str] = None, ied_id: Optional[str] = None, custom_mapping: Optional[Dict[str, str]] = None) -> ValidationResult:
        return ValidationResult(
            target_entity_id=bay_id,
            valid=True,
            violations=[],
            checks_performed=[],
            metadata={"ablation": "Validator disabled; undetected violations"},
        )


class DisabledHistoryTool(HistoryTool):
    async def execute(self, feeder_id: str, limit: int = 3) -> HistoricalIncidentResult:
        return HistoricalIncidentResult(query_feeder_id=feeder_id, matching_incidents=[])


class VectorOnlyRetrievalTool(RetrievalTool):
    async def execute(self, query: str, top_k: int = 4) -> DocumentRetrievalResult:
        return await self.engine.retrieve(query=query, top_k=top_k, use_dense=True, use_lexical=False)


class LexicalOnlyRetrievalTool(RetrievalTool):
    async def execute(self, query: str, top_k: int = 4) -> DocumentRetrievalResult:
        return await self.engine.retrieve(query=query, top_k=top_k, use_dense=False, use_lexical=True)


class SystemEvaluator:
    """Automated benchmark evaluator computing empirical metrics across Baseline, GridLens, and Ablations."""

    @classmethod
    async def _evaluate_workflow(
        cls,
        workflow: GridLensInvestigationWorkflow,
        system_name: str,
        test_cases: Optional[List[GoldenTestCase]] = None
    ) -> EvaluationRunReport:
        if test_cases is None:
            test_cases = EvaluationDataset.get_all_test_cases()

        detailed = []
        passed = 0
        diag_passed = 0
        tool_passed = 0
        abstain_passed = 0
        abstention_cases = 0
        false_abstentions = 0
        sufficient_cases = 0
        contradiction_passed = 0
        contradiction_cases = 0
        unsupported_claims = 0
        candidate_claims = 0
        latencies = []

        with INCIDENTS_FILE.open("r", encoding="utf-8") as f:
            incidents_seed = json.load(f)
        inc_map = {inc["incident_id"]: inc for inc in incidents_seed}

        for tc in test_cases:
            t0 = time.time()
            req = InvestigationRequest(
                investigation_id=f"EVAL-{tc.case_id}",
                incident_id=tc.target_incident_id,
                user_query=tc.query,
                target_equipment_id=tc.target_feeder_id,
            )
            inc_data = inc_map.get(tc.target_incident_id)
            result = await workflow.run_investigation(req, incident_data=inc_data)
            duration_ms = (time.time() - t0) * 1000.0
            latencies.append(duration_ms)

            # Check diagnostic criteria
            top_hyp_code = result.hypotheses[0].code if result.hypotheses else "NONE"
            diag_ok = (top_hyp_code == tc.expected_top_hypothesis_code)
            suff_ok = (result.is_sufficient == tc.expected_sufficiency)
            inv_type_ok = (result.investigation_type.value == tc.expected_investigation_type)
            observed_tools = [
                trace.tool_invoked for trace in result.execution_trace
                if trace.tool_invoked
            ]
            tool_ok = observed_tools == tc.expected_tool_calls
            all_claim_text = " ".join([
                result.diagnosis_title,
                result.sufficiency_reason,
                result.diagnosis_summary,
                result.conflict_explanation or "",
                *(citation.content for citation in result.citations),
                *(claim.statement for claim in result.verified_facts + result.supported_inferences),
            ]).lower()
            facts_ok = all(keyword.lower() in all_claim_text for keyword in tc.expected_fact_keywords)

            case_success = diag_ok and suff_ok and inv_type_ok and facts_ok and tool_ok
            if case_success:
                passed += 1
            if diag_ok and facts_ok:
                diag_passed += 1
            if tool_ok:
                tool_passed += 1
            if tc.expected_sufficiency:
                sufficient_cases += 1
                if not result.is_sufficient:
                    false_abstentions += 1
            if not tc.expected_sufficiency:
                abstention_cases += 1
            if suff_ok and not tc.expected_sufficiency and not result.is_sufficient:
                abstain_passed += 1
            if tc.category == "CONTRADICTION_HANDLING":
                contradiction_cases += 1
            if tc.category == "CONTRADICTION_HANDLING" and result.conflict_lifecycle.value in {
                "CONFLICT_RESOLVED", "CONFLICT_UNRESOLVED"
            }:
                contradiction_passed += 1

            unsupported_claims += len(result.rejected_claims)
            candidate_claims += len(result.verified_facts) + len(result.supported_inferences) + len(result.rejected_claims)

            detailed.append({
                "case_id": tc.case_id,
                "category": tc.category,
                "query": tc.query,
                "passed": case_success,
                "investigation_type": result.investigation_type.value,
                "expected_type": tc.expected_investigation_type,
                "top_hypothesis": top_hyp_code,
                "expected_hypothesis": tc.expected_top_hypothesis_code,
                "is_sufficient": result.is_sufficient,
                "expected_sufficiency": tc.expected_sufficiency,
                "observed_tools": observed_tools,
                "expected_tools": tc.expected_tool_calls,
                "tool_selection_ok": tool_ok,
                "fact_keywords_ok": facts_ok,
                "duration_ms": round(duration_ms, 1),
            })

        total = len(test_cases)
        sorted_lats = sorted(latencies) if latencies else []
        p95_lat = sorted_lats[int(round(0.95 * (len(sorted_lats) - 1)))] if sorted_lats else 0.0

        metrics = EvaluationMetrics(
            total_test_cases=total,
            passed_cases=passed,
            accuracy_percent=round((passed / total) * 100.0, 1),
            diagnosis_accuracy_percent=round((diag_passed / total) * 100.0, 1),
            tool_selection_accuracy_percent=round((tool_passed / total) * 100.0, 1),
            abstention_accuracy_percent=round((abstain_passed / abstention_cases) * 100.0, 1) if abstention_cases else 100.0,
            false_abstention_percent=round((false_abstentions / sufficient_cases) * 100.0, 1) if sufficient_cases else 0.0,
            contradiction_detection_percent=round((contradiction_passed / contradiction_cases) * 100.0, 1) if contradiction_cases else 100.0,
            unsupported_claim_rate_percent=round((unsupported_claims / candidate_claims) * 100.0, 1) if candidate_claims else 0.0,
            avg_latency_ms=round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
            latency_p95_ms=round(p95_lat, 1),
        )

        return EvaluationRunReport(
            system_name=system_name,
            metrics=metrics,
            detailed_results=detailed,
        )

    @classmethod
    async def _evaluate_naive_baseline(cls, baseline: Any, test_cases: List[GoldenTestCase]) -> EvaluationRunReport:
        passed = 0
        diag_passed = 0
        abstain_passed = 0
        abstention_cases = 0
        false_abstentions = 0
        sufficient_cases = 0
        contradiction_cases = 0
        contradiction_passed = 0
        unsupported_claims = 0
        candidate_claims = 0
        latencies = []

        for tc in test_cases:
            t0 = time.time()
            res = await baseline.execute_case(tc.case_id, tc.query, tc.target_incident_id)
            dur = (time.time() - t0) * 1000.0
            latencies.append(dur)

            diag_ok = (res.predicted_hypothesis == tc.expected_top_hypothesis_code)
            suff_ok = ((not res.abstained) == tc.expected_sufficiency)
            if tc.expected_sufficiency:
                sufficient_cases += 1
                if res.abstained:
                    false_abstentions += 1
            if not tc.expected_sufficiency:
                abstention_cases += 1
                if res.abstained:
                    abstain_passed += 1

            if tc.category == "CONTRADICTION_HANDLING":
                contradiction_cases += 1

            if not res.is_faithful:
                unsupported_claims += len(res.faithfulness_violations)
            candidate_claims += max(res.candidate_claim_count, 1)

            if diag_ok and suff_ok:
                passed += 1
                diag_passed += 1

        total = len(test_cases)
        sorted_lats = sorted(latencies) if latencies else []
        p95_lat = sorted_lats[int(round(0.95 * (len(sorted_lats) - 1)))] if sorted_lats else 0.0

        return EvaluationRunReport(
            system_name="Scripted heuristic negative control (no LLM)",
            metrics=EvaluationMetrics(
                total_test_cases=total,
                passed_cases=passed,
                accuracy_percent=round((passed / total) * 100.0, 1) if total else 0.0,
                diagnosis_accuracy_percent=round((diag_passed / total) * 100.0, 1) if total else 0.0,
                tool_selection_accuracy_percent=0.0,
                abstention_accuracy_percent=round((abstain_passed / abstention_cases) * 100.0, 1) if abstention_cases else 0.0,
                false_abstention_percent=round((false_abstentions / sufficient_cases) * 100.0, 1) if sufficient_cases else 0.0,
                contradiction_detection_percent=round((contradiction_passed / contradiction_cases) * 100.0, 1) if contradiction_cases else 0.0,
                unsupported_claim_rate_percent=round((unsupported_claims / candidate_claims) * 100.0, 1) if candidate_claims else 0.0,
                avg_latency_ms=round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
                latency_p95_ms=round(p95_lat, 1),
            ),
            detailed_results=[],
        )

    @classmethod
    async def evaluate_full_gridlens(cls) -> EvaluationRunReport:
        workflow = GridLensInvestigationWorkflow()
        return await cls._evaluate_workflow(workflow, "Full GridLens (Agent + Graph + COMTRADE + Validator + RAG)")

    @classmethod
    async def evaluate_latent_cases(cls, split: str = "dev") -> EvaluationRunReport:
        """Compatibility entry point: now executes fresh physical CFG/DAT cases."""
        from services.evaluation.physical_cases import evaluate_physical
        physical = await evaluate_physical(split)
        return EvaluationRunReport(
            system_name=f"Generated physical inputs ({split}); not diagnostic-generalization accuracy",
            metrics=EvaluationMetrics(total_test_cases=physical["cases"], passed_cases=physical["passed"],
                                      accuracy_percent=100 * physical["passed"] / physical["cases"],
                                      physical_accuracy_percent=100 * physical["passed"] / physical["cases"]),
            detailed_results=physical["results"])

    @classmethod
    async def get_comparative_benchmark(cls) -> Dict[str, Any]:
        """Dynamically computes the empirical comparison matrix by systematically executing ablations."""
        # 1. Full GridLens
        full_report = await cls.evaluate_full_gridlens()

        # 2. Ablation A: No Graph
        wf_no_graph = GridLensInvestigationWorkflow(topology_tool=DisabledTopologyTool())
        rep_no_graph = await cls._evaluate_workflow(wf_no_graph, "Ablation A (No Graph)")

        # 3. Ablation B: No COMTRADE
        wf_no_wav = GridLensInvestigationWorkflow(waveform_tool=DisabledWaveformTool())
        rep_no_wav = await cls._evaluate_workflow(wf_no_wav, "Ablation B (No COMTRADE)")

        # 4. Ablation C: No Validator
        wf_no_val = GridLensInvestigationWorkflow(validation_tool=DisabledValidationTool())
        rep_no_val = await cls._evaluate_workflow(wf_no_val, "Ablation C (No Validator)")

        # 5. Ablation D: No History
        wf_no_hist = GridLensInvestigationWorkflow(history_tool=DisabledHistoryTool())
        rep_no_hist = await cls._evaluate_workflow(wf_no_hist, "Ablation D (No History)")

        # 6. Ablation E: Vector-Only RAG (No BM25 lexical)
        wf_vec_only = GridLensInvestigationWorkflow(retrieval_tool=VectorOnlyRetrievalTool())
        rep_vec_only = await cls._evaluate_workflow(wf_vec_only, "Ablation E (Vector-Only Retrieval)")

        # 7. Ablation F: Lexical-Only RAG (No dense vectors)
        wf_lex_only = GridLensInvestigationWorkflow(retrieval_tool=LexicalOnlyRetrievalTool())
        rep_lex_only = await cls._evaluate_workflow(wf_lex_only, "Ablation F (Lexical-Only Retrieval)")

        # 8. Scripted negative control: not a model comparison
        from services.evaluation.naive_baseline import NaiveBaseline
        test_cases = EvaluationDataset.get_all_test_cases()
        baseline = NaiveBaseline()
        rep_baseline = await cls._evaluate_naive_baseline(baseline, test_cases)

        comparison_matrix = [
            {
                "system": "Scripted heuristic negative control (no LLM)",
                "diagnosis_accuracy": rep_baseline.metrics.diagnosis_accuracy_percent,
                "tool_selection_accuracy": rep_baseline.metrics.tool_selection_accuracy_percent,
                "contradiction_detection": rep_baseline.metrics.contradiction_detection_percent,
                "abstention_accuracy": rep_baseline.metrics.abstention_accuracy_percent,
                "unsupported_claim_rate": rep_baseline.metrics.unsupported_claim_rate_percent,
                "avg_latency_ms": rep_baseline.metrics.avg_latency_ms,
                "key_limitation": "Produces ungrounded measurements and cannot resolve topology or secondary wiring swaps.",
            },
            {
                "system": "Ablation A (No Graph)",
                "diagnosis_accuracy": rep_no_graph.metrics.accuracy_percent,
                "tool_selection_accuracy": rep_no_graph.metrics.tool_selection_accuracy_percent,
                "contradiction_detection": rep_no_graph.metrics.contradiction_detection_percent,
                "abstention_accuracy": rep_no_graph.metrics.abstention_accuracy_percent,
                "unsupported_claim_rate": rep_no_graph.metrics.unsupported_claim_rate_percent,
                "avg_latency_ms": rep_no_graph.metrics.avg_latency_ms,
                "key_limitation": "Fails on feeder-breaker associations, bay boundaries, and upstream infeed context.",
            },
            {
                "system": "Ablation B (No COMTRADE)",
                "diagnosis_accuracy": rep_no_wav.metrics.accuracy_percent,
                "tool_selection_accuracy": rep_no_wav.metrics.tool_selection_accuracy_percent,
                "contradiction_detection": rep_no_wav.metrics.contradiction_detection_percent,
                "abstention_accuracy": rep_no_wav.metrics.abstention_accuracy_percent,
                "unsupported_claim_rate": rep_no_wav.metrics.unsupported_claim_rate_percent,
                "avg_latency_ms": rep_no_wav.metrics.avg_latency_ms,
                "key_limitation": "Cannot verify physical RMS fault currents, wave shape, or clearing time intervals.",
            },
            {
                "system": "Ablation C (No Validator)",
                "diagnosis_accuracy": rep_no_val.metrics.accuracy_percent,
                "tool_selection_accuracy": rep_no_val.metrics.tool_selection_accuracy_percent,
                "contradiction_detection": rep_no_val.metrics.contradiction_detection_percent,
                "abstention_accuracy": rep_no_val.metrics.abstention_accuracy_percent,
                "unsupported_claim_rate": rep_no_val.metrics.unsupported_claim_rate_percent,
                "avg_latency_ms": rep_no_val.metrics.avg_latency_ms,
                "key_limitation": "Blinds system to secondary CT polarity and channel mapping inversion in Incident B.",
            },
            {
                "system": "Ablation D (No History)",
                "diagnosis_accuracy": rep_no_hist.metrics.accuracy_percent,
                "tool_selection_accuracy": rep_no_hist.metrics.tool_selection_accuracy_percent,
                "contradiction_detection": rep_no_hist.metrics.contradiction_detection_percent,
                "abstention_accuracy": rep_no_hist.metrics.abstention_accuracy_percent,
                "unsupported_claim_rate": rep_no_hist.metrics.unsupported_claim_rate_percent,
                "avg_latency_ms": rep_no_hist.metrics.avg_latency_ms,
                "key_limitation": "Lacks past recurring fault signatures and previous bay maintenance records.",
            },
            {
                "system": "Ablation E (Vector-Only Retrieval)",
                "diagnosis_accuracy": rep_vec_only.metrics.accuracy_percent,
                "tool_selection_accuracy": rep_vec_only.metrics.tool_selection_accuracy_percent,
                "contradiction_detection": rep_vec_only.metrics.contradiction_detection_percent,
                "abstention_accuracy": rep_vec_only.metrics.abstention_accuracy_percent,
                "unsupported_claim_rate": rep_vec_only.metrics.unsupported_claim_rate_percent,
                "avg_latency_ms": rep_vec_only.metrics.avg_latency_ms,
                "key_limitation": "Decreased recall on exact alphanumeric engineering identifiers without BM25.",
            },
            {
                "system": "Ablation F (Lexical-Only Retrieval)",
                "diagnosis_accuracy": rep_lex_only.metrics.accuracy_percent,
                "tool_selection_accuracy": rep_lex_only.metrics.tool_selection_accuracy_percent,
                "contradiction_detection": rep_lex_only.metrics.contradiction_detection_percent,
                "abstention_accuracy": rep_lex_only.metrics.abstention_accuracy_percent,
                "unsupported_claim_rate": rep_lex_only.metrics.unsupported_claim_rate_percent,
                "avg_latency_ms": rep_lex_only.metrics.avg_latency_ms,
                "key_limitation": "Reduced semantic recall on paraphrased conceptual queries without dense vectors.",
            },
            {
                "system": "Full GridLens",
                "diagnosis_accuracy": full_report.metrics.accuracy_percent,
                "tool_selection_accuracy": full_report.metrics.tool_selection_accuracy_percent,
                "contradiction_detection": full_report.metrics.contradiction_detection_percent,
                "abstention_accuracy": full_report.metrics.abstention_accuracy_percent,
                "unsupported_claim_rate": full_report.metrics.unsupported_claim_rate_percent,
                "avg_latency_ms": full_report.metrics.avg_latency_ms,
                "key_limitation": "Scoped to seeded substation protection configurations and IEEE COMTRADE scope.",
            },
        ]

        out = {
            "baseline": rep_baseline.model_dump() if hasattr(rep_baseline, "model_dump") else rep_baseline.dict(),
            "full_gridlens": full_report.model_dump() if hasattr(full_report, "model_dump") else full_report.dict(),
            "comparison_matrix": comparison_matrix,
        }

        try:
            from services.config import DATA_ROOT
            eval_dir = DATA_ROOT / "evaluation"
            eval_dir.mkdir(parents=True, exist_ok=True)
            with open(eval_dir / "benchmark_results.json", "w", encoding="utf-8") as f:
                json.dump(out, f, indent=2)
        except Exception:
            pass

        return out
