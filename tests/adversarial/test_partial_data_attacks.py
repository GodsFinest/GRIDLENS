"""Adversarial Track 1: Partial Data & Truncation Attacks.

Tests that the Sufficiency Policy Gate fails closed (abstains) when presented with
truncated waveforms, missing CT ratios, missing SOE records, or incomplete topology.
Target: 0% False Diagnosis (100% abstention on deficient data).
"""
import pytest
from domain.investigation.models import InvestigationRequest, InvestigationType
from domain.evidence.models import Evidence, EvidenceKind, EvidenceSourceType
from services.agent.sufficiency import SufficiencyPolicyEngine
from services.agent.graph import GridLensInvestigationWorkflow


def test_sufficiency_gate_abstains_on_truncated_waveform():
    """Truncated waveform (duration < 50ms or is_truncated flag) must trigger abstention."""
    evidence_with_truncated_comtrade = [
        Evidence(
            evidence_id="EV_COMTRADE_TRUNCATED",
            kind=EvidenceKind.RECORDING_TRUNCATED,
            source_type=EvidenceSourceType.COMTRADE,
            source_id="INC-TRUNC.DAT",
            tool_name="WaveformTool",
            fact="COMTRADE recording was truncated after 30 ms (buffer error).",
            structured_value=True,
            provenance="COMTRADE header analysis",
            deterministic=True,
        ),
        Evidence(
            evidence_id="EV_TOPO_PRIMARY_RELAY",
            kind=EvidenceKind.TOPO_PRIMARY_RELAY,
            source_type=EvidenceSourceType.GRAPH,
            source_id="IN_MEMORY_TOPOLOGY",
            tool_name="TopologyTool",
            fact="RELAY_12 is primary protection.",
            structured_value="RELAY_12",
            provenance="Topology",
            deterministic=True,
        ),
    ]

    is_suff, reason, missing = SufficiencyPolicyEngine.evaluate_sufficiency(
        InvestigationType.PROTECTION_EVENT_INVESTIGATION,
        evidence_with_truncated_comtrade,
    )

    assert is_suff is False, "Sufficiency gate must fail closed on truncated waveform"
    assert "truncated" in reason.lower()
    assert any("truncated" in m.lower() or "waveform" in m.lower() or "comtrade" in m.lower() for m in missing)


def test_sufficiency_gate_abstains_on_missing_topology():
    """Missing topology associations must trigger abstention."""
    evidence_missing_topo = [
        Evidence(
            evidence_id="EV_TOPO_MISSING",
            kind=EvidenceKind.TOPO_MISSING,
            source_type=EvidenceSourceType.GRAPH,
            source_id="IN_MEMORY_TOPOLOGY",
            tool_name="TopologyTool",
            fact="Feeder F99 topology is incomplete.",
            structured_value=False,
            provenance="Topology",
            deterministic=True,
        ),
    ]

    is_suff, reason, missing = SufficiencyPolicyEngine.evaluate_sufficiency(
        InvestigationType.TOPOLOGY_INQUIRY,
        evidence_missing_topo,
    )

    assert is_suff is False, "Sufficiency gate must fail closed when topology is incomplete"
    assert "required" in reason.lower() or "insufficient" in reason.lower()
    assert any("topology" in m.lower() for m in missing)


def test_sufficiency_gate_abstains_on_zero_evidence():
    """Zero evidence must fail closed immediately."""
    is_suff, reason, missing = SufficiencyPolicyEngine.evaluate_sufficiency(
        InvestigationType.PROTECTION_EVENT_INVESTIGATION,
        [],
    )

    assert is_suff is False
    assert len(missing) > 0


@pytest.mark.asyncio
async def test_workflow_end_to_end_abstains_on_incident_c():
    """Full workflow on Incident C (truncated oscillography) must conclude with INSUFFICIENT_EVIDENCE."""
    workflow = GridLensInvestigationWorkflow()
    req = InvestigationRequest(
        investigation_id="ATK_PARTIAL_INC3",
        incident_id="INC-2026-003",
        user_query="Why did feeder F13 trip?",
        target_equipment_id="F13",
    )

    result = await workflow.run_investigation(req)

    assert result.is_sufficient is False, "Workflow must abstain on Incident C"
    assert "INSUFFICIENT" in result.diagnosis_title.upper() or "ABSTAINED" in result.diagnosis_title.upper()
    assert len(result.missing_evidence) > 0
    # Must NOT guess a root cause with high confidence
    assert result.confidence_score <= 0.35, f"Confidence score must be low under abstention, got {result.confidence_score}"
