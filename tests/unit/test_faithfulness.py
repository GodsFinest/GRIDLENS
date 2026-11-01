"""Unit tests verifying FaithfulnessVerifier and ClaimVerifier paraphrase semantics."""
from domain.claims.models import Claim, ClaimType, VerificationStatus
from domain.evidence.models import Evidence, EvidenceKind, EvidenceSourceType
from services.agent.faithfulness import FaithfulnessVerifier
from services.agent.verifier import ClaimVerifier


def test_faithfulness_verifier_accepts_grounded_narrative():
    claims = [
        Claim(
            claim_id="C01",
            statement="RELAY_12 is configured as the primary protection relay for Feeder F12.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV1"],
        ),
        Claim(
            claim_id="C02",
            statement="Feeder F12 is controlled by circuit breaker CB12 on BUS_B.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV2"],
        ),
        Claim(
            claim_id="C03",
            statement="Channel IC measured Pre-fault RMS: 240.08 A, Fault RMS: 3758.63 A (Peak: 5315.0 A).",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV3"],
        ),
    ]

    narrative = (
        "GridLens Investigation Finding: GENUINE PRIMARY FEEDER OVERCURRENT FAULT.\n\n"
        "Feeder F12 was protected by primary relay RELAY_12 and vacuum breaker CB12 on BUS_B. "
        "During the fault, Channel IC reached a physical Fault RMS of 3758.63 A from a pre-fault level of 240.08 A."
    )

    # Free prose is not an entailment oracle. The supported narrative contract
    # is complete verified quotations, preserving polarity and subject binding.
    for claim in claims:
        claim.verification_status = VerificationStatus.VERIFIED
    narrative = "\n".join(c.statement for c in claims)
    is_faithful, violations = FaithfulnessVerifier.verify_faithfulness(narrative, claims)
    assert is_faithful is True
    assert len(violations) == 0


def test_faithfulness_verifier_rejects_unsupported_entity():
    claims = [
        Claim(
            claim_id="C01",
            statement="RELAY_12 is configured as the primary protection relay for Feeder F12.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV1"],
        ),
    ]

    narrative = "Primary relay RELAY_12 tripped breaker CB99 on Feeder F12."
    is_faithful, violations = FaithfulnessVerifier.verify_faithfulness(narrative, claims)
    assert is_faithful is False
    assert any("CB99" in v for v in violations)


def test_faithfulness_verifier_rejects_unsupported_quantity():
    claims = [
        Claim(
            claim_id="C01",
            statement="Channel IC measured Fault RMS: 3758.63 A.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV1"],
        ),
    ]

    # Narrative invents a 4800 A fault current (well beyond 0.5% tolerance)
    narrative = "The recorded fault surge reached 4800.0 A on Phase C."
    is_faithful, violations = FaithfulnessVerifier.verify_faithfulness(narrative, claims)
    assert is_faithful is False
    assert any("4800.0 A" in v for v in violations)


def test_faithfulness_does_not_accept_prose_from_quantity_similarity_alone():
    claims = [
        Claim(
            claim_id="C01",
            statement="Channel IC measured Fault RMS: 3758.63 A.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV1"],
        ),
    ]

    # Narrative rounds 3758.63 to 3758.0 A (0.016% difference, well within 0.5% tolerance)
    narrative = "The recorded fault surge reached 3758.0 A on Phase C."
    is_faithful, violations = FaithfulnessVerifier.verify_faithfulness(narrative, claims, tolerance_pct=0.5)
    assert is_faithful is False
    assert violations


def test_claim_verifier_paraphrase_matching():
    ev = Evidence(
        evidence_id="EV_TOPO_01",
        kind=EvidenceKind.TOPO_PRIMARY_RELAY,
        source_type=EvidenceSourceType.GRAPH,
        source_id="GRAPH",
        tool_name="TopologyTool",
        fact="RELAY_12 is configured as the primary protection relay for Feeder F12.",
        structured_value="RELAY_12",
        provenance="Directed graph query",
        deterministic=True,
    )

    # 1. Close paraphrase with similarity >= 0.70
    paraphrase_claim = Claim(
        claim_id="C10",
        statement="Feeder F12 has primary protection relay configured as RELAY_12.",
        claim_type=ClaimType.FACT,
        evidence_ids=["EV_TOPO_01"],
    )

    v_facts, s_infs, r_claims = ClaimVerifier.verify_candidate_claims([paraphrase_claim], [ev])
    assert len(v_facts) == 1
    assert v_facts[0].verification_status == VerificationStatus.VERIFIED

    # 2. Distant statement with similarity < 0.70
    unrelated_claim = Claim(
        claim_id="C11",
        statement="Transformer T1 supplies high voltage to the industrial switchyard.",
        claim_type=ClaimType.FACT,
        evidence_ids=["EV_TOPO_01"],
    )

    v_facts2, s_infs2, r_claims2 = ClaimVerifier.verify_candidate_claims([unrelated_claim], [ev])
    assert len(r_claims2) == 1
    assert r_claims2[0].verification_status == VerificationStatus.REJECTED
