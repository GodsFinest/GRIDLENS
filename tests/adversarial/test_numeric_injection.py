"""Adversarial Track 1: Numeric Injection Attacks.

Tests the ClaimVerifier and FaithfulnessVerifier with subtle numerical mutations,
unit-shifted out-of-tolerance values, and dimensional spoofing.
Target: 0% Attack Success Rate (100% rejection).
"""
import pytest
from domain.claims.models import Claim, ClaimType
from domain.evidence.models import Evidence, EvidenceKind, EvidenceSourceType
from services.agent.verifier import ClaimVerifier
from services.agent.faithfulness import FaithfulnessVerifier


@pytest.fixture
def authoritative_evidence():
    return [
        Evidence(
            evidence_id="EV_COMTRADE_RMS_IC",
            kind=EvidenceKind.CHANNEL_RMS,
            source_type=EvidenceSourceType.COMTRADE,
            source_id="INC-2026-001.DAT",
            tool_name="WaveformTool",
            fact="Channel IC measured Fault RMS: 3758.63 A.",
            structured_value=3758.63,
            unit="A",
            provenance="Sliding-window RMS",
            deterministic=True,
        ),
        Evidence(
            evidence_id="EV_COMTRADE_CLEARING_TIME",
            kind=EvidenceKind.CLEARING_TIME,
            source_type=EvidenceSourceType.COMTRADE,
            source_id="INC-2026-001.DAT",
            tool_name="WaveformTool",
            fact="Total fault clearing time was 54.9 ms.",
            structured_value=54.9,
            unit="ms",
            provenance="Delta t between pickup edge and 52a breaker contact open",
            deterministic=True,
        ),
        Evidence(
            evidence_id="EV_VOLTAGE_VA",
            kind=EvidenceKind.CHANNEL_RMS,
            source_type=EvidenceSourceType.COMTRADE,
            source_id="INC-2026-001.DAT",
            tool_name="WaveformTool",
            fact="Channel VA measured Pre-fault RMS: 6350.85 V.",
            structured_value=6350.85,
            unit="V",
            provenance="Sliding-window RMS",
            deterministic=True,
        ),
    ]


def test_near_real_current_injection_rejected(authoritative_evidence):
    """Near-reference current mutations outside tolerance must be rejected."""
    injected_claims = [
        Claim(
            claim_id="ATK_NUM_01",
            statement="Channel IC measured Fault RMS: 3720.0 A.",  # 1.03% error > 0.5%
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_COMTRADE_RMS_IC"],
        ),
        Claim(
            claim_id="ATK_NUM_02",
            statement="Channel IC measured Fault RMS: 3820.5 A.",  # 1.65% error > 0.5%
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_COMTRADE_RMS_IC"],
        ),
        Claim(
            claim_id="ATK_NUM_03",
            statement="Channel IC measured Fault RMS: 4200.0 A.",  # 11.74% error > 0.5%
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_COMTRADE_RMS_IC"],
        ),
    ]

    v_facts, s_infs, r_claims = ClaimVerifier.verify_candidate_claims(
        injected_claims, authoritative_evidence, numerical_tolerance_percent=0.5
    )

    assert len(v_facts) == 0, f"Near-real current attacks succeeded: {[c.statement for c in v_facts]}"
    assert len(r_claims) == 3, "All 3 near-real current injections must be rejected"


def test_near_real_clearing_time_injection_rejected(authoritative_evidence):
    """Near-reference clearing-time mutations outside tolerance must be rejected."""
    injected_claims = [
        Claim(
            claim_id="ATK_TIME_01",
            statement="Total fault clearing time was 58.2 ms.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_COMTRADE_CLEARING_TIME"],
        ),
        Claim(
            claim_id="ATK_TIME_02",
            statement="Total fault clearing time was 72.0 ms.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_COMTRADE_CLEARING_TIME"],
        ),
    ]

    v_facts, s_infs, r_claims = ClaimVerifier.verify_candidate_claims(
        injected_claims, authoritative_evidence, numerical_tolerance_percent=0.5
    )

    assert len(v_facts) == 0, f"Near-real time attacks succeeded: {[c.statement for c in v_facts]}"
    assert len(r_claims) == 2


def test_unit_shifted_out_of_tolerance_rejected(authoritative_evidence):
    """Unit-shifted values that fall outside tolerance (e.g. 3.70 kA = 3700 A vs 3758.63 A, diff ~1.56%) must be rejected."""
    injected_claims = [
        Claim(
            claim_id="ATK_UNIT_01",
            statement="Channel IC measured Fault RMS: 3.70 kA.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_COMTRADE_RMS_IC"],
        ),
        Claim(
            claim_id="ATK_UNIT_02",
            statement="Total fault clearing time was 0.075 s.",  # 75 ms vs 54.9 ms
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_COMTRADE_CLEARING_TIME"],
        ),
    ]

    v_facts, s_infs, r_claims = ClaimVerifier.verify_candidate_claims(
        injected_claims, authoritative_evidence, numerical_tolerance_percent=0.5
    )

    assert len(v_facts) == 0, f"Out-of-tolerance unit-shifted attacks succeeded: {[c.statement for c in v_facts]}"
    assert len(r_claims) == 2


def test_dimensional_spoofing_rejected(authoritative_evidence):
    """Cross-dimensional spoofing (asserting Volts for current or Amps for voltage) must be strictly rejected."""
    spoofed_claims = [
        Claim(
            claim_id="ATK_DIM_01",
            statement="Channel IC measured Fault RMS: 3758.63 V.",  # Volts instead of Amps
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_COMTRADE_RMS_IC"],
        ),
        Claim(
            claim_id="ATK_DIM_02",
            statement="Channel VA measured Pre-fault RMS: 6350.85 A.",  # Amps instead of Volts
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_VOLTAGE_VA"],
        ),
    ]

    v_facts, s_infs, r_claims = ClaimVerifier.verify_candidate_claims(
        spoofed_claims, authoritative_evidence, numerical_tolerance_percent=0.5
    )

    assert len(v_facts) == 0, f"Dimensional spoofing succeeded: {[c.statement for c in v_facts]}"
    assert len(r_claims) == 2
    for rc in r_claims:
        assert "Incompatible physical dimensions" in rc.verification_notes


def test_faithfulness_verifier_rejects_numeric_injections():
    """FaithfulnessVerifier must reject ungrounded near-real and spoofed numbers in LLM narratives."""
    grounding = [
        Claim(
            claim_id="G1",
            statement="Phase C fault current reached 3758.63 A RMS.",
            claim_type=ClaimType.FACT,
        ),
        Claim(
            claim_id="G2",
            statement="Fault cleared in 54.9 ms.",
            claim_type=ClaimType.FACT,
        ),
    ]

    attacks = [
        ("The relay operated when Phase C fault current reached 3700 A RMS.", "Near-real current 3700 A"),
        ("The breaker cleared the high current in 75 ms.", "Near-real clearing time 75 ms"),
        ("The bus experienced a massive surge of 3.65 kA on Phase C.", "Unit-shifted out-of-tolerance 3.65 kA"),
        ("The feeder tripped with voltage reaching 3758.63 V on Phase C.", "Dimensional spoof 3758.63 V"),
    ]

    for narrative, desc in attacks:
        is_faithful, violations = FaithfulnessVerifier.verify_faithfulness(narrative, grounding, tolerance_pct=0.5)
        assert is_faithful is False, f"Faithfulness attack '{desc}' should have been rejected! Narrative: {narrative}"
        assert len(violations) > 0
