"""Unit tests for SI unit canonicalization and dimensional comparison in services/agent/units.py."""
from services.agent.units import (
    PhysicalDimension,
    parse_unit,
    canonicalize_quantity,
    are_quantities_compatible,
)


def test_parse_unit_dimensions():
    # Current
    assert parse_unit("A")[0] == PhysicalDimension.CURRENT
    assert parse_unit("kA")[0] == PhysicalDimension.CURRENT
    assert parse_unit("mA")[0] == PhysicalDimension.CURRENT
    assert parse_unit("Amps")[0] == PhysicalDimension.CURRENT

    # Voltage
    assert parse_unit("V")[0] == PhysicalDimension.VOLTAGE
    assert parse_unit("kV")[0] == PhysicalDimension.VOLTAGE
    assert parse_unit("mV")[0] == PhysicalDimension.VOLTAGE
    assert parse_unit("Volts")[0] == PhysicalDimension.VOLTAGE

    # Time
    assert parse_unit("s")[0] == PhysicalDimension.TIME
    assert parse_unit("ms")[0] == PhysicalDimension.TIME
    assert parse_unit("milliseconds")[0] == PhysicalDimension.TIME

    # Frequency
    assert parse_unit("Hz")[0] == PhysicalDimension.FREQUENCY
    assert parse_unit("kHz")[0] == PhysicalDimension.FREQUENCY

    # Unknown
    assert parse_unit("frobs") is None


def test_canonicalize_quantity_current_conversions():
    # 3.75863 kA -> 3758.63 A
    val, unit, dim = canonicalize_quantity(3.75863, "kA")
    assert round(val, 2) == 3758.63
    assert unit == "A"
    assert dim == PhysicalDimension.CURRENT

    # 500 mA -> 0.5 A
    val, unit, dim = canonicalize_quantity(500.0, "mA")
    assert round(val, 3) == 0.5
    assert unit == "A"


def test_canonicalize_quantity_voltage_conversions():
    # 11.0 kV -> 11000 V
    val, unit, dim = canonicalize_quantity(11.0, "kV")
    assert val == 11000.0
    assert unit == "V"
    assert dim == PhysicalDimension.VOLTAGE

    # 100 mV -> 0.1 V
    val, unit, dim = canonicalize_quantity(100.0, "mV")
    assert round(val, 3) == 0.1
    assert unit == "V"


def test_canonicalize_quantity_time_conversions():
    # 54.9 ms -> 0.0549 s
    val, unit, dim = canonicalize_quantity(54.9, "ms")
    assert round(val, 4) == 0.0549
    assert unit == "s"
    assert dim == PhysicalDimension.TIME

    # 1.5 s -> 1.5 s
    val, unit, dim = canonicalize_quantity(1.5, "s")
    assert val == 1.5
    assert unit == "s"


def test_are_quantities_compatible_same_unit():
    matched, _ = are_quantities_compatible(3758.63, "A", 3758.0, "A", tolerance_pct=0.5)
    assert matched is True

    # Out of tolerance (1.5% diff with 0.5% tolerance)
    matched, reason = are_quantities_compatible(3758.63, "A", 3700.0, "A", tolerance_pct=0.5)
    assert matched is False
    assert "Value mismatch" in reason


def test_are_quantities_compatible_prefix_conversions():
    # kA to A
    matched, reason = are_quantities_compatible(3.75863, "kA", 3758.63, "A", tolerance_pct=0.1)
    assert matched is True, f"Prefix kA <-> A should match: {reason}"

    # A to kA
    matched, reason = are_quantities_compatible(3758.63, "A", 3.75863, "kA", tolerance_pct=0.1)
    assert matched is True

    # kV to V
    matched, reason = are_quantities_compatible(11.0, "kV", 11000.0, "V", tolerance_pct=0.1)
    assert matched is True

    # ms to s
    matched, reason = are_quantities_compatible(54.9, "ms", 0.0549, "s", tolerance_pct=0.1)
    assert matched is True


def test_are_quantities_compatible_dimension_mismatch_rejected():
    # Current vs Voltage: 3758 A vs 3.758 kV (same base magnitude if scaled, but wrong physical dimension)
    matched, reason = are_quantities_compatible(3758.0, "A", 3.758, "kV", tolerance_pct=1.0)
    assert matched is False
    assert "Incompatible physical dimensions" in reason

    # Current vs Voltage: 3758 A vs 3758 V
    matched, reason = are_quantities_compatible(3758.0, "A", 3758.0, "V", tolerance_pct=1.0)
    assert matched is False
    assert "Incompatible physical dimensions" in reason

    # Time vs Current: 54.9 ms vs 54.9 A
    matched, reason = are_quantities_compatible(54.9, "ms", 54.9, "A", tolerance_pct=1.0)
    assert matched is False
    assert "Incompatible physical dimensions" in reason


def test_claim_verifier_accepts_unit_prefix_conversion():
    from domain.claims.models import Claim, ClaimType
    from domain.evidence.models import Evidence, EvidenceKind, EvidenceSourceType
    from services.agent.verifier import ClaimVerifier

    ev = Evidence(
        evidence_id="EV_COMTRADE_RMS_IC",
        kind=EvidenceKind.CHANNEL_RMS,
        source_type=EvidenceSourceType.COMTRADE,
        source_id="INC-2026-001.DAT",
        tool_name="WaveformTool",
        fact="Channel IC measured Pre-fault RMS: 241.06 A, Fault RMS: 3758.63 A (Peak: 5882.12 A).",
        structured_value=3758.63,
        unit="A",
        provenance="Sliding-window RMS calculation on channel IC",
        deterministic=True,
    )

    # Claim states current in kA instead of A: 3.75863 kA == 3758.63 A
    claim_ka = Claim(
        claim_id="C_KA",
        statement="Channel IC measured Pre-fault RMS: 241.06 A, Fault RMS: 3.75863 kA (Peak: 5882.12 A).",
        claim_type=ClaimType.FACT,
        evidence_ids=["EV_COMTRADE_RMS_IC"],
    )

    v_facts, s_infs, r_claims = ClaimVerifier.verify_candidate_claims([claim_ka], [ev])
    assert len(v_facts) == 1, f"Claim with 3.75863 kA should be verified: {claim_ka.verification_notes}"
    assert len(r_claims) == 0


def test_claim_verifier_rejects_dimension_mismatch():
    from domain.claims.models import Claim, ClaimType
    from domain.evidence.models import Evidence, EvidenceKind, EvidenceSourceType
    from services.agent.verifier import ClaimVerifier

    ev = Evidence(
        evidence_id="EV_COMTRADE_RMS_IC",
        kind=EvidenceKind.CHANNEL_RMS,
        source_type=EvidenceSourceType.COMTRADE,
        source_id="INC-2026-001.DAT",
        tool_name="WaveformTool",
        fact="Channel IC measured Pre-fault RMS: 241.06 A, Fault RMS: 3758.63 A (Peak: 5882.12 A).",
        structured_value=3758.63,
        unit="A",
        provenance="Sliding-window RMS calculation on channel IC",
        deterministic=True,
    )

    # Claim asserts Volts instead of Amps: 3758 V
    claim_v = Claim(
        claim_id="C_V",
        statement="Channel IC measured Pre-fault RMS: 241.06 V, Fault RMS: 3758.63 V (Peak: 5882.12 V).",
        claim_type=ClaimType.FACT,
        evidence_ids=["EV_COMTRADE_RMS_IC"],
    )

    v_facts, s_infs, r_claims = ClaimVerifier.verify_candidate_claims([claim_v], [ev])
    assert len(r_claims) == 1, "Claim asserting Volts instead of Amps must be rejected"
    assert "Incompatible physical dimensions" in r_claims[0].verification_notes


def test_faithfulness_verifier_unit_prefix_conversion():
    from domain.claims.models import Claim, ClaimType
    from services.agent.faithfulness import FaithfulnessVerifier

    grounding_claim = Claim(
        claim_id="C1",
        statement="Phase C fault current reached 3758.63 A RMS.",
        claim_type=ClaimType.FACT,
    )

    # Narrative uses kA prefix: 3.75863 kA
    narrative_ka = "The system experienced a major disturbance where Phase C fault current reached 3.75863 kA RMS."
    is_faithful, violations = FaithfulnessVerifier.verify_faithfulness(narrative_ka, [grounding_claim])
    # Unit equivalence alone does not establish the other assertions in prose.
    # Positive unit-conversion coverage is in ClaimVerifier's bound templates.
    assert is_faithful is False
    assert violations

    # Narrative uses wrong dimension: 3758.63 V
    narrative_v = "The system experienced a voltage surge of 3758.63 V."
    is_faithful, violations = FaithfulnessVerifier.verify_faithfulness(narrative_v, [grounding_claim])
    assert is_faithful is False, "Narrative with 3758.63 V should NOT match 3758.63 A"
    assert any("Ungrounded measurement" in v for v in violations)


def test_derived_quantity_cross_check():
    from domain.claims.models import Claim, ClaimType
    from domain.evidence.models import Evidence, EvidenceKind, EvidenceSourceType
    from services.agent.verifier import ClaimVerifier

    ev_pri = Evidence(
        evidence_id="EV_COMTRADE_RMS_IC",
        kind=EvidenceKind.CHANNEL_RMS,
        source_type=EvidenceSourceType.COMTRADE,
        source_id="INC-2026-001.DAT",
        tool_name="WaveformTool",
        fact="Channel IC measured Fault RMS: 3758.63 A.",
        structured_value=3758.63,
        unit="A",
        provenance="Sliding-window RMS",
        metadata={"channel": "IC", "ct_ratio": 240.0},
        deterministic=True,
    )

    # Expected secondary current: 3758.63 / 240.0 = 15.66 A
    claim_valid_sec = Claim(
        claim_id="C_SEC_OK",
        statement="Channel IC secondary RMS current = 15.66 A.",
        claim_type=ClaimType.FACT,
        evidence_ids=["EV_COMTRADE_RMS_IC"],
    )

    # Unsupported secondary current: 18.50 A
    claim_bad_sec = Claim(
        claim_id="C_SEC_BAD",
        statement="Channel IC secondary RMS current = 18.50 A.",
        claim_type=ClaimType.FACT,
        evidence_ids=["EV_COMTRADE_RMS_IC"],
    )

    v_facts, s_infs, r_claims = ClaimVerifier.verify_candidate_claims([claim_valid_sec, claim_bad_sec], [ev_pri])
    assert any(c.claim_id == "C_SEC_OK" for c in v_facts), "Valid derived secondary current must be verified"
    assert any(c.claim_id == "C_SEC_BAD" for c in r_claims), "Invalid derived secondary current must be rejected"
    bad_notes = next(c.verification_notes for c in r_claims if c.claim_id == "C_SEC_BAD")
    assert "Rejected" in bad_notes

