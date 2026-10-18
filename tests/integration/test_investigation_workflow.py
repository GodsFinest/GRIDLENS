"""Integration tests for the seeded incident workflows."""
import json
import pytest
from domain.investigation.models import InvestigationRequest
from domain.claims.models import ConflictLifecycle
from services.agent.graph import GridLensInvestigationWorkflow


@pytest.mark.asyncio
async def test_incident_a_investigation():
    workflow = GridLensInvestigationWorkflow()
    with open("data/seed/incidents.json", "r") as f:
        incidents = json.load(f)
    inc_a = next(i for i in incidents if i["incident_id"] == "INC-2026-001")

    req = InvestigationRequest(
        incident_id="INC-2026-001",
        user_query="Why did feeder F12 trip at 14:32?",
    )
    result = await workflow.run_investigation(req, incident_data=inc_a)

    assert result.is_sufficient is True
    assert result.hypotheses[0].code == "H1"
    assert result.confidence_score >= 0.80
    assert result.conflict_lifecycle == ConflictLifecycle.NO_CONFLICT
    assert len(result.verified_facts) > 0
    assert any("IC" in f.statement or "Phase C" in f.statement for f in result.verified_facts)
    assert len(result.supported_inferences) > 0


@pytest.mark.asyncio
async def test_compiled_langgraph_router_executes_when_available():
    workflow = GridLensInvestigationWorkflow()
    if workflow._compiled_graph is None:
        pytest.skip("LangGraph optional dependency is not installed in this environment.")

    request = InvestigationRequest(user_query="Which relay protects feeder F12?")
    result = await workflow.run_investigation(request)

    assert result.investigation_type.value == "TOPOLOGY_INQUIRY"
    assert result.verified_facts
    assert result.verified_facts[0].verification_status.value == "VERIFIED"


@pytest.mark.asyncio
async def test_incident_b_contradiction_resolution():
    workflow = GridLensInvestigationWorkflow()
    with open("data/seed/incidents.json", "r") as f:
        incidents = json.load(f)
    inc_b = next(i for i in incidents if i["incident_id"] == "INC-2026-002")

    req = InvestigationRequest(
        incident_id="INC-2026-002",
        user_query="Investigate deceptive phase trip in incident B with conflicting relay flag and waveform.",
    )
    result = await workflow.run_investigation(req, incident_data=inc_b)

    assert result.is_sufficient is True
    assert result.hypotheses[0].code == "H3"
    assert result.conflict_lifecycle == ConflictLifecycle.CONFLICT_RESOLVED
    assert any("RULE-MAP-003" in f.statement for f in result.verified_facts)


@pytest.mark.asyncio
async def test_incident_c_insufficient_evidence_abstention():
    workflow = GridLensInvestigationWorkflow()
    with open("data/seed/incidents.json", "r") as f:
        incidents = json.load(f)
    inc_c = next(i for i in incidents if i["incident_id"] == "INC-2026-003")

    req = InvestigationRequest(
        incident_id="INC-2026-003",
        user_query="Why did feeder F13 trip?",
    )
    result = await workflow.run_investigation(req, incident_data=inc_c)

    assert result.is_sufficient is False
    assert result.hypotheses[0].code == "H6"
    assert "INSUFFICIENT" in result.diagnosis_title.upper()
    assert len(result.missing_evidence) > 0


@pytest.mark.asyncio
async def test_incident_e_settings_misoperation_selects_h2():
    """Verify INC-2026-005 selects H2 (Settings Misoperation) while INC-001 selects H1 and INC-002 selects H3."""
    workflow = GridLensInvestigationWorkflow()
    with open("data/seed/incidents.json", "r") as f:
        incidents = json.load(f)
    inc_e = next(i for i in incidents if i["incident_id"] == "INC-2026-005")

    req = InvestigationRequest(
        incident_id="INC-2026-005",
        user_query="Why did feeder F12 trip on load inrush in incident INC-2026-005?",
    )
    result = await workflow.run_investigation(req, incident_data=inc_e)

    assert result.is_sufficient is True
    assert result.hypotheses[0].code == "H2", f"Expected H2, got {result.hypotheses[0].code}"
    assert "Misoperation" in result.diagnosis_title
    assert result.conflict_lifecycle == ConflictLifecycle.NO_CONFLICT

