"""Adversarial Track 1: Entity-Swap Attacks.

Attacks the ClaimVerifier and FaithfulnessVerifier by substituting wrong apparatus identifiers
(e.g. CB13, RELAY_11, BUS_A) into claims and narratives concerning Feeder F12 / CB12 / RELAY_12.
Target: 0% Attack Success Rate (100% rejection).
"""
import pytest
from domain.claims.models import Claim, ClaimType, VerificationStatus
from domain.evidence.models import Evidence, EvidenceKind, EvidenceSourceType
from services.agent.verifier import ClaimVerifier
from services.agent.faithfulness import FaithfulnessVerifier


@pytest.fixture
def f12_evidence():
    return [
        Evidence(
            evidence_id="EV_TOPO_BREAKER",
            kind=EvidenceKind.TOPO_BREAKER,
            source_type=EvidenceSourceType.GRAPH,
            source_id="IN_MEMORY_TOPOLOGY",
            tool_name="TopologyTool",
            fact="Feeder F12 is controlled by circuit breaker CB12 on BUS_B.",
            structured_value="CB12",
            provenance="Bay BAY_F12 breaker association",
            deterministic=True,
        ),
        Evidence(
            evidence_id="EV_TOPO_PRIMARY_RELAY",
            kind=EvidenceKind.TOPO_PRIMARY_RELAY,
            source_type=EvidenceSourceType.GRAPH,
            source_id="IN_MEMORY_TOPOLOGY",
            tool_name="TopologyTool",
            fact="RELAY_12 is configured as the primary protection relay for Feeder F12.",
            structured_value="RELAY_12",
            provenance="Substation OGS-01 -> Bay BAY_F12 -> F12",
            deterministic=True,
        ),
    ]


def test_claim_verifier_rejects_swapped_breakers(f12_evidence):
    """Claims asserting wrong circuit breakers (CB13, CB11, CB14, CB21) must be rejected."""
    swapped_breakers = ["CB11", "CB13", "CB14", "CB21", "CB22"]
    claims = [
        Claim(
            claim_id=f"ATK_CB_{cb}",
            statement=f"Feeder F12 is controlled by circuit breaker {cb} on BUS_B.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_TOPO_BREAKER"],
        )
        for cb in swapped_breakers
    ]

    v_facts, s_infs, r_claims = ClaimVerifier.verify_candidate_claims(claims, f12_evidence)

    assert len(v_facts) == 0, f"Breaker swap attacks succeeded: {[c.statement for c in v_facts]}"
    assert len(r_claims) == len(swapped_breakers), "All swapped breaker claims must be rejected"
    for rc in r_claims:
        assert "references ungrounded equipment" in rc.verification_notes


def test_claim_verifier_rejects_swapped_relays(f12_evidence):
    """Claims asserting wrong relays (RELAY_11, RELAY_13) must be rejected."""
    swapped_relays = ["RELAY_11", "RELAY_13"]
    claims = [
        Claim(
            claim_id=f"ATK_RELAY_{r}",
            statement=f"{r} is configured as the primary protection relay for Feeder F12.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_TOPO_PRIMARY_RELAY"],
        )
        for r in swapped_relays
    ]

    v_facts, s_infs, r_claims = ClaimVerifier.verify_candidate_claims(claims, f12_evidence)

    assert len(v_facts) == 0, f"Relay swap attacks succeeded: {[c.statement for c in v_facts]}"
    assert len(r_claims) == len(swapped_relays), "All swapped relay claims must be rejected"
    for rc in r_claims:
        assert "references ungrounded equipment" in rc.verification_notes


def test_claim_verifier_rejects_swapped_buses(f12_evidence):
    """Claims asserting wrong bus (BUS_A instead of BUS_B) must be rejected."""
    claim_bus_a = Claim(
        claim_id="ATK_BUS_A",
        statement="Feeder F12 is controlled by circuit breaker CB12 on BUS_A.",
        claim_type=ClaimType.FACT,
        evidence_ids=["EV_TOPO_BREAKER"],
    )

    v_facts, s_infs, r_claims = ClaimVerifier.verify_candidate_claims([claim_bus_a], f12_evidence)

    assert len(v_facts) == 0, "Bus A swap should be rejected"
    assert len(r_claims) == 1
    assert "references ungrounded equipment" in r_claims[0].verification_notes


def test_faithfulness_verifier_rejects_entity_swaps():
    """FaithfulnessVerifier must reject ungrounded entity substitutions in LLM narratives."""
    grounding = [
        Claim(
            claim_id="G1",
            statement="Feeder F12 is controlled by breaker CB12.",
            claim_type=ClaimType.FACT,
        ),
        Claim(
            claim_id="G2",
            statement="Primary protection relay is RELAY_12 on BUS_B.",
            claim_type=ClaimType.FACT,
        ),
    ]

    swapped_narratives = [
        ("Feeder F12 tripped when circuit breaker CB13 failed to open.", "CB13 swap"),
        ("The overcurrent fault was cleared by RELAY_11 on the bay.", "RELAY_11 swap"),
        ("The fault propagated upstream causing disconnection of BUS_A.", "BUS_A swap"),
        ("Sensor CT13A registered abnormal current during the incident.", "CT13A swap"),
    ]

    for narrative, desc in swapped_narratives:
        is_faithful, violations = FaithfulnessVerifier.verify_faithfulness(narrative, grounding)
        assert is_faithful is False, f"Entity swap '{desc}' should have been rejected! Narrative: {narrative}"
        assert any("Ungrounded entity" in v for v in violations)
