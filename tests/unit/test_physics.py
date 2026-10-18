"""Tests for fault classification, counterfactuals, and settings checks."""
import pytest

from services.physics.symmetrical import classify_from_rms, classify_from_measurements
from services.physics.counterfactual import (
    CounterfactualInput,
    describe_scenario_change,
    simulate,
)
from services.physics.settings_advisor import SettingProposal, evaluate


# --- Phasor path: all four fault classes + balanced load --------------------


def test_phasor_balanced_load():
    res = classify_from_measurements({"A": (240, 0), "B": (240, -120), "C": (240, 120)})
    assert res.fault_type == "BALANCED"
    assert res.faulted_phase == "NONE"
    assert res.sequence_trusted is True
    assert res.i0_mag < 1.0  # true zero sequence of balanced set


def test_phasor_lg_phase_c():
    res = classify_from_measurements({"A": (240, 0), "B": (240, -120), "C": (3758, 120)})
    assert res.fault_type == "C-G (LG)"
    assert res.faulted_phase == "C"
    # Ground fault: zero and negative sequence comparable to positive.
    assert res.i0_mag > 1000
    assert res.i1_mag > 1000


def test_phasor_ll_phases_180_apart_not_llg():
    """True B-C phase-to-phase fault: faulted phases ~180 deg apart.

    Regression test for the fabricated-I0 bug: magnitudes alone with an
    assumed 120 deg separation yield a phantom ~1 kA zero-sequence and a
    false LLG label. True phasors give small I0 and an LL label.
    """
    res = classify_from_measurements({"A": (240, 0), "B": (3000, -90), "C": (3000, 90)})
    assert res.fault_type == "B-C (LL)"
    assert res.faulted_phase == "BC"
    assert res.i0_mag < 0.15 * res.i1_mag
    assert "LLG" not in res.fault_type


def test_phasor_llg_ground_involvement():
    res = classify_from_measurements({"A": (1500, 0), "B": (3000, -90), "C": (3000, 90)})
    assert res.fault_type == "B-C-G (LLG)"
    assert res.i0_mag > 0.15 * res.i1_mag


def test_phasor_three_phase_balanced_fault():
    """Balanced overcurrent is a three-phase fault, not 'no fault'."""
    res = classify_from_measurements({"A": (3500, 0), "B": (3500, -120), "C": (3500, 120)})
    assert res.fault_type == "3-PH"
    assert res.faulted_phase == "ABC"


# --- RMS triage path ---------------------------------------------------------


def test_rms_balanced_load():
    res = classify_from_rms(240.0, 241.0, 239.0)
    assert res.fault_type == "BALANCED"
    assert res.sequence_trusted is False


def test_rms_single_dominant_phase_is_lg_triage():
    res = classify_from_rms(240.0, 240.0, 3758.0)
    assert "LG" in res.fault_type
    assert res.sequence_trusted is False
    assert res.i0_mag == 0.0  # never fabricated from magnitudes


def test_rms_two_phases_ambiguous_never_llg():
    """RMS magnitudes cannot resolve LL vs LLG: must say so, not guess."""
    res = classify_from_rms(240.0, 3000.0, 3000.0)
    assert "LLG" not in res.fault_type.replace("LL or LLG", "")
    assert "phasor" in res.fault_type.lower() or "phasor" in res.explanation.lower()
    assert res.sequence_trusted is False
    assert res.i0_mag == 0.0


def test_rms_balanced_overcurrent_is_three_phase():
    res = classify_from_rms(3500.0, 3500.0, 3500.0)
    assert "3-PH" in res.fault_type
    assert res.faulted_phase == "ABC"


# --- Counterfactual ------------------------------------------------------------


def test_counterfactual_matches_physics():
    res = simulate(CounterfactualInput(r_line=0.18, x_line=0.72, r_fault=0.05))
    assert res.fault_current_a > 2500
    assert res.would_trip is True
    assert res.clearing_time_ms > res.operating_time_ms
    assert str(int(res.fault_current_a)) in res.narrative_numbers


def test_counterfactual_high_impedance_no_trip():
    res = simulate(CounterfactualInput(r_line=0.1, x_line=0.3, r_fault=100.0))
    assert res.would_trip is False


def test_describe_scenario_change():
    assert describe_scenario_change(0.05, 0.10) == "fault resistance 0.05 -> 0.1 ohm (x2.00)"


# --- Setting advisor: all branches ----------------------------------------------


def test_setting_advisor_rejects_spurious_pickup():
    # INC-2026-005 analogue: 500A pickup on 630A-rated feeder.
    v = evaluate(SettingProposal(pickup_a=500.0, time_dial=0.1), max_load_a=630.0, min_fault_a=3758.0)
    assert v.valid is False
    assert any("too low" in m for m in v.violations)


def test_setting_advisor_rejects_insensitive_pickup():
    # Pickup so high the minimum fault is missed (sensitivity < 1.5).
    v = evaluate(SettingProposal(pickup_a=3000.0, time_dial=0.1), max_load_a=630.0, min_fault_a=3758.0)
    assert v.valid is False
    assert any("sensitivity" in m for m in v.violations)


def test_setting_advisor_accepts_sane_setting():
    v = evaluate(SettingProposal(pickup_a=2500.0, time_dial=0.1), max_load_a=630.0, min_fault_a=3758.0)
    assert v.valid is True
    assert v.sensitivity >= 1.5
    assert v.load_margin >= 1.25


# --- Tool-level guards ------------------------------------------------------------


@pytest.mark.asyncio
async def test_physics_tool_skips_setting_check_below_pickup():
    """Below pickup there is no fault to be sensitive to (H2 path, not sensitivity)."""
    from services.tools.physics_tool import PhysicsTool

    res = await PhysicsTool().execute_symmetrical(
        incident_id="INC-2026-005", feeder_id="F12",
        phase_rms={"A": 550.0, "B": 550.0, "C": 550.0},
        pickup_a=2500.0, max_load_a=630.0,
    )
    assert res.setting_verdict is None
    assert "below pickup" in (res.setting_check_skipped_reason or "")


@pytest.mark.asyncio
async def test_physics_tool_skipped_without_three_phases():
    from services.tools.physics_tool import PhysicsTool

    res = await PhysicsTool().execute_symmetrical(
        incident_id="INC-2026-003", feeder_id="F13",
        phase_rms={"A": 180.0}, pickup_a=2500.0, max_load_a=400.0,
    )
    assert res.classification is None
    assert res.classification_basis == "SKIPPED"


# --- Workflow integration ----------------------------------------------------


@pytest.mark.asyncio
async def test_event_investigation_runs_physics_tool_and_ledgers_facts():
    """The workflow records physics results in the evidence ledger."""
    from domain.investigation.models import InvestigationRequest
    from services.agent.graph import GridLensInvestigationWorkflow

    workflow = GridLensInvestigationWorkflow()
    req = InvestigationRequest(incident_id="INC-2026-001", user_query="Why did feeder F12 trip at 14:32?")
    result = await workflow.run_investigation(req)

    ledger = getattr(result, "_evidence_ledger", [])
    kinds = {ev.kind.value if hasattr(ev.kind, "value") else str(ev.kind) for ev in ledger}
    assert "FAULT_CLASSIFICATION" in kinds
    tools = [t.tool_invoked for t in result.execution_trace if t.tool_invoked]
    assert "PhysicsTool" in tools
    assert any("LG" in c.statement for c in result.verified_facts)
