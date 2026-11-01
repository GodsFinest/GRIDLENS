"""Unit tests for offline trace exporter in services/agent/trace_exporter.py."""
import pytest
from domain.investigation.models import InvestigationRequest
from services.agent.graph import GridLensInvestigationWorkflow
from services.agent.trace_exporter import (
    export_investigation_trace,
    validate_trace_schema,
    save_trace_to_file,
)


@pytest.mark.asyncio
async def test_trace_exporter_end_to_end(tmp_path):
    workflow = GridLensInvestigationWorkflow()
    req = InvestigationRequest(
        investigation_id="TRACE-TEST-001",
        incident_id="INC-2026-001",
        user_query="Why did feeder F12 trip at 14:32?",
        target_equipment_id="F12",
    )

    result = await workflow.run_investigation(req)
    trace = export_investigation_trace(result)

    # 1. Structural schema validation
    assert validate_trace_schema(trace) is True, "Exported trace must satisfy schema validation"
    assert trace["investigation_id"] == "TRACE-TEST-001"
    assert trace["run_type"] == "chain"
    assert "spans" in trace
    assert len(trace["spans"]) == len(result.execution_trace)

    # 2. Inspect child spans
    span_names = [s["name"] for s in trace["spans"]]
    assert "INTENT_CLASSIFICATION_AND_TOOL_SELECTION" in span_names
    assert "WAVEFORM_ANALYSIS" in span_names
    assert "SYNTHESIZE_REPORT" in span_names

    # 3. Inspect outputs
    outputs = trace["outputs"]
    assert outputs["is_sufficient"] is True
    assert outputs["verified_facts_count"] > 0
    assert outputs["rejected_claims_count"] == 0

    # 4. File serialization check
    out_file = tmp_path / "test_trace.json"
    saved_path = save_trace_to_file(result, out_file)
    assert saved_path.exists()
    assert saved_path.stat().st_size > 500
