"""Integration tests verifying load-bearing compiled LangGraph execution and audit provenance."""
import pytest
from domain.investigation.models import InvestigationRequest, InvestigationType
from services.agent.graph import GridLensInvestigationWorkflow


@pytest.mark.asyncio
async def test_compiled_graph_topology_inquiry_skips_unreachable_tool_nodes():
    """Verify TOPOLOGY_INQUIRY executes only TopologyTool and never touches WaveformTool or HistoryTool."""
    workflow = GridLensInvestigationWorkflow()
    assert workflow._compiled_graph is not None, "Compiled StateGraph must be active"

    req = InvestigationRequest(
        user_query="Which circuit breaker protects feeder F12?",
    )
    result = await workflow.run_investigation(req)

    assert result.investigation_type == InvestigationType.TOPOLOGY_INQUIRY
    assert result.is_sufficient is True

    # Audit trace verification: derive executed stages from the actual node runs
    stages_executed = [entry.stage for entry in result.execution_trace]
    tools_executed = [entry.tool_invoked for entry in result.execution_trace if entry.tool_invoked]

    # Must contain topology stage and tool
    assert "TOPOLOGY_EXTRACTION" in stages_executed
    assert "TopologyTool" in tools_executed

    # Must NEVER contain waveform, physics, history, or validation tools
    assert "WaveformTool" not in tools_executed
    assert "PhysicsTool" not in tools_executed
    assert "HistoryTool" not in tools_executed
    assert "ValidationTool" not in tools_executed
    assert "WAVEFORM_ANALYSIS" not in stages_executed
    assert "PHYSICS_ANALYSIS" not in stages_executed
    assert "HISTORY_CORRELATION" not in stages_executed

    # Assert node ordering: CLASSIFY -> TOPOLOGY -> ASSESS -> SUFFICIENCY -> CONSTRUCT -> VERIFY -> SYNTHESIZE
    expected_order = [
        "INTENT_CLASSIFICATION_AND_TOOL_SELECTION",
        "TOPOLOGY_EXTRACTION",
        "ASSESS_EVIDENCE",
        "RESOLVE_CONFLICTS",
        "SUFFICIENCY_GATE",
        "CONSTRUCT_CLAIMS",
        "VERIFY_CLAIMS",
        "SYNTHESIZE_REPORT",
    ]
    assert stages_executed == expected_order


@pytest.mark.asyncio
async def test_compiled_graph_protection_event_full_traversal():
    """Verify PROTECTION_EVENT_INVESTIGATION traverses all 7 tool nodes in sequence."""
    workflow = GridLensInvestigationWorkflow()

    req = InvestigationRequest(
        incident_id="INC-2026-001",
        user_query="Why did feeder F12 trip at 14:32?",
    )
    result = await workflow.run_investigation(req)

    assert result.investigation_type == InvestigationType.PROTECTION_EVENT_INVESTIGATION
    assert result.is_sufficient is True

    tools_executed = [entry.tool_invoked for entry in result.execution_trace if entry.tool_invoked]
    assert tools_executed == [
        "TopologyTool",
        "WaveformTool",
        "PhysicsTool",
        "ValidationTool",
        "SOETool",
        "RetrievalTool",
        "HistoryTool",
    ]

    # Every trace entry must have realistic non-zero or positive duration and timestamps
    for entry in result.execution_trace:
        assert entry.step_index > 0
        assert entry.timestamp is not None
        assert entry.duration_ms >= 0.0
        assert entry.outputs_summary != ""


@pytest.mark.asyncio
async def test_topology_inquiry_f13_with_incident_context_precedence():
    """Regression test: TOPOLOGY_INQUIRY for F13 must investigate F13 even when incident_data is INC-2026-001 (F12)."""
    import json
    from services.config import INCIDENTS_FILE

    with INCIDENTS_FILE.open("r", encoding="utf-8") as f:
        incidents = json.load(f)
    inc_001 = next(inc for inc in incidents if inc["incident_id"] == "INC-2026-001")

    workflow = GridLensInvestigationWorkflow()

    # Query 1: Relay protecting F13
    req_relay = InvestigationRequest(
        user_query="Which relay protects feeder F13?",
        target_equipment_id="F13",
        incident_id="INC-2026-001",
    )
    res_relay = await workflow.run_investigation(req_relay, incident_data=inc_001)
    assert res_relay.investigation_type == InvestigationType.TOPOLOGY_INQUIRY
    relay_facts = [f.statement for f in res_relay.verified_facts]
    assert any("RELAY_13" in st for st in relay_facts), f"Expected RELAY_13 in verified facts: {relay_facts}"

    # Query 2: Breaker associated with F13
    req_cb = InvestigationRequest(
        user_query="Which circuit breaker is associated with feeder F13?",
        target_equipment_id="F13",
        incident_id="INC-2026-001",
    )
    res_cb = await workflow.run_investigation(req_cb, incident_data=inc_001)
    assert res_cb.investigation_type == InvestigationType.TOPOLOGY_INQUIRY
    cb_facts = [f.statement for f in res_cb.verified_facts]
    assert any("CB13" in st for st in cb_facts), f"Expected CB13 in verified facts: {cb_facts}"

