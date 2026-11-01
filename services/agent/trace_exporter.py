"""Offline structured JSON trace exporter for GridLens investigation execution graphs.

Generates an offline LangSmith / OpenTelemetry-compatible span and run hierarchy
tracking workflow execution, individual tool calls, verifier verdicts, and latencies.
"""
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List
from domain.investigation.models import InvestigationResult


def export_investigation_trace(result: InvestigationResult) -> Dict[str, Any]:
    """
    Exports an InvestigationResult into a structured, offline LangSmith-compatible run trace.
    """
    run_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, result.investigation_id))
    child_spans: List[Dict[str, Any]] = []

    for idx, step in enumerate(result.execution_trace):
        span_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{result.investigation_id}-step-{idx}"))
        is_tool = bool(step.tool_invoked)
        is_llm = "prose" in step.stage.lower() or "synthesize" in step.stage.lower()
        span_type = "tool" if is_tool else ("llm" if is_llm else "chain")

        child_spans.append({
            "id": span_id,
            "parent_run_id": run_id,
            "name": step.stage,
            "run_type": span_type,
            "tool_name": step.tool_invoked,
            "inputs": step.inputs,
            "outputs": {"summary": step.outputs_summary},
            "status": "SUCCESS",
            "duration_ms": round(step.duration_ms, 2),
            "step_index": idx + 1,
            "timestamp": step.timestamp,
        })

    trace_payload = {
        "id": run_id,
        "name": f"GridLensInvestigationWorkflow:{result.investigation_type.value}",
        "run_type": "chain",
        "investigation_id": result.investigation_id,
        "incident_id": result.incident_id,
        "investigation_type": result.investigation_type.value,
        "start_time": result.created_at,
        "total_duration_ms": result.duration_ms,
        "inputs": {
            "user_query": result.user_query,
            "incident_id": result.incident_id,
            "investigation_type": result.investigation_type.value,
        },
        "outputs": {
            "diagnosis_title": result.diagnosis_title,
            "confidence_score": result.confidence_score,
            "is_sufficient": result.is_sufficient,
            "is_faithful": result.is_faithful,
            "verified_facts_count": len(result.verified_facts),
            "supported_inferences_count": len(result.supported_inferences),
            "rejected_claims_count": len(result.rejected_claims),
            "conflict_lifecycle": result.conflict_lifecycle.value,
        },
        "tags": [
            "gridlens",
            "offline-trace",
            result.investigation_type.value.lower().replace("_", "-"),
            "sufficient" if result.is_sufficient else "abstained",
        ],
        "spans": child_spans,
        "metadata": {
            "schema_version": "1.0.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "hypotheses_count": len(result.hypotheses),
            "citations_count": len(result.citations),
        },
    }

    return trace_payload


def save_trace_to_file(result: InvestigationResult, output_path: Path) -> Path:
    """Serializes trace dictionary to a JSON file."""
    trace_data = export_investigation_trace(result)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(trace_data, f, indent=2)
    return output_path


def validate_trace_schema(trace_dict: Dict[str, Any]) -> bool:
    """Validates structural integrity of an exported trace dictionary."""
    required_root_keys = {
        "id", "name", "run_type", "investigation_id", "investigation_type",
        "start_time", "total_duration_ms", "inputs", "outputs", "spans", "tags", "metadata"
    }
    if not required_root_keys.issubset(trace_dict.keys()):
        return False

    required_span_keys = {"id", "parent_run_id", "name", "run_type", "duration_ms", "status"}
    for span in trace_dict.get("spans", []):
        if not required_span_keys.issubset(span.keys()):
            return False

    return True
