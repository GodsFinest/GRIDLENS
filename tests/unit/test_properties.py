"""Property-based tests using Hypothesis for power systems signals and state machine invariants."""
import math
import numpy as np
import pytest
from hypothesis import given, strategies as st, settings
from domain.claims.models import ConflictLifecycle, ConflictTracker, Claim, ClaimType
from services.agent.faithfulness import FaithfulnessVerifier


# --- Property 1: Conflict Lifecycle Invariants ---
@given(
    st.lists(
        st.sampled_from([
            ConflictLifecycle.NO_CONFLICT,
            ConflictLifecycle.CONFLICT_DETECTED,
            ConflictLifecycle.INVESTIGATION,
            ConflictLifecycle.CONFLICT_RESOLVED,
            ConflictLifecycle.CONFLICT_UNRESOLVED,
        ]),
        min_size=1,
        max_size=10,
    )
)
def test_property_conflict_lifecycle_valid_transitions_only(states):
    """Verifies that ConflictTracker NEVER permits an invalid state machine transition."""
    tracker = ConflictTracker()
    allowed_transitions = {
        ConflictLifecycle.NO_CONFLICT: {ConflictLifecycle.CONFLICT_DETECTED},
        ConflictLifecycle.CONFLICT_DETECTED: {ConflictLifecycle.INVESTIGATION},
        ConflictLifecycle.INVESTIGATION: {ConflictLifecycle.CONFLICT_RESOLVED, ConflictLifecycle.CONFLICT_UNRESOLVED},
        ConflictLifecycle.CONFLICT_RESOLVED: set(),
        ConflictLifecycle.CONFLICT_UNRESOLVED: set(),
    }

    for next_st in states:
        current = tracker.current_state
        if next_st in allowed_transitions[current]:
            # Valid transition must succeed
            tracker.advance_conflict(next_state=next_st, rule_id="TEST-RULE", evidence_ids=["EV1"], explanation="Test transition")
            assert tracker.current_state == next_st
        else:
            # Illegal transition MUST raise ValueError
            with pytest.raises(ValueError):
                tracker.advance_conflict(next_state=next_st, rule_id="TEST-RULE", evidence_ids=["EV1"], explanation="Illegal")


# --- Property 2: Faithfulness Verifier Rejects Fabricated Quantities ---
@given(
    st.floats(min_value=100.0, max_value=50000.0, allow_nan=False, allow_infinity=False),
    st.floats(min_value=0.02, max_value=0.90, allow_nan=False, allow_infinity=False),  # 2% to 90% error
    st.booleans(),
)
@settings(max_examples=50)
def test_property_faithfulness_rejects_mutated_measurements(ledger_val, error_ratio, positive_error):
    """Reject measurements whose error exceeds the configured tolerance."""
    multiplier = (1.0 + error_ratio) if positive_error else (1.0 - error_ratio)
    mutated_val = round(ledger_val * multiplier, 2)

    # Ensure difference is strictly outside 0.5% tolerance
    if abs(mutated_val - ledger_val) <= 0.005 * ledger_val + 0.1:
        return

    claim = Claim(
        claim_id="C_PROP",
        statement=f"Channel IC measured Fault RMS: {round(ledger_val, 2)} A.",
        claim_type=ClaimType.FACT,
        evidence_ids=["EV_PROP"],
    )

    narrative = f"The physical fault current reached {mutated_val} A on Phase C."
    is_faithful, violations = FaithfulnessVerifier.verify_faithfulness(
        narrative=narrative,
        grounding_claims=[claim],
        tolerance_pct=0.5,
    )

    assert is_faithful is False, f"Expected rejection of {mutated_val} A against ledger {ledger_val} A"
    assert len(violations) > 0


# --- Property 3: Sinusoidal Signal RMS Non-Negativity ---
@given(
    freq=st.floats(min_value=45.0, max_value=65.0),
    phase_deg=st.floats(min_value=-180.0, max_value=180.0),
    amplitude=st.floats(min_value=0.0, max_value=50000.0),
)
@settings(max_examples=50)
def test_property_rms_non_negativity(freq, phase_deg, amplitude):
    """Verifies that RMS calculated over any sinusoidal waveform is strictly non-negative and <= peak."""
    fs = 4000.0  # 4 kHz sampling
    t = np.linspace(0.0, 0.2, int(0.2 * fs), endpoint=False)
    phase_rad = math.radians(phase_deg)
    signal = amplitude * np.sin(2.0 * np.pi * freq * t + phase_rad)

    rms = np.sqrt(np.mean(signal**2))
    assert rms >= 0.0
    # True RMS of pure sine wave is amplitude / sqrt(2)
    expected_rms = amplitude / math.sqrt(2.0)
    assert abs(rms - expected_rms) <= max(0.05 * expected_rms, 1.0)
