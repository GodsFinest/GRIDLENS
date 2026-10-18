"""Regression tests for unsupported numerical and entity claims."""
import pytest
from domain.claims.models import Claim, ClaimType, VerificationStatus
from domain.evidence.models import Evidence, EvidenceSourceType
from services.agent.verifier import ClaimVerifier


def test_fact_with_real_evidence_id_but_fabricated_statement_is_rejected():
    evidence = Evidence(
        evidence_id="EV_CURRENT",
        source_type=EvidenceSourceType.COMTRADE,
        source_id="INC-1.DAT",
        tool_name="WaveformTool",
        fact="Channel IC measured Fault RMS: 3758.63 A.",
        structured_value=3758.63,
        unit="A",
        provenance="Analyzer",
    )
    claim = Claim(
        claim_id="C01",
        statement="Channel IC measured Fault RMS: 3850 A.",
        claim_type=ClaimType.FACT,
        evidence_ids=[evidence.evidence_id],
    )
    facts, inferences, rejected = ClaimVerifier.verify_candidate_claims([claim], [evidence])
    assert facts == []
    assert inferences == []
    assert rejected[0].verification_status == VerificationStatus.REJECTED


def test_verifier_rejects_unsupported_numerical_current():
    evidence = Evidence(
        evidence_id="EV_CURRENT_RMS",
        source_type=EvidenceSourceType.COMTRADE,
        source_id="INC-1.DAT",
        tool_name="WaveformTool",
        fact="Channel IC measured Fault RMS: 3758.63 A.",
        structured_value=3758.63,
        unit="A",
        provenance="Analyzer",
    )
    candidate_claim = Claim(
        claim_id="C02",
        statement="Phase C peak fault current surged to 4800 A during the feeder disturbance.",
        claim_type=ClaimType.FACT,
        evidence_ids=[evidence.evidence_id],
    )
    facts, inferences, rejected = ClaimVerifier.verify_candidate_claims([candidate_claim], [evidence])
    assert len(facts) == 0
    assert len(rejected) == 1
    assert rejected[0].verification_status == VerificationStatus.REJECTED
    assert "Numerical assertion mismatch" in rejected[0].verification_notes
    assert "4800" in rejected[0].verification_notes


def test_verifier_catches_ungrounded_breaker_entity():
    evidence = Evidence(
        evidence_id="EV_TOPO_BREAKER",
        source_type=EvidenceSourceType.GRAPH,
        source_id="IN_MEMORY_TOPOLOGY",
        tool_name="TopologyTool",
        fact="Feeder F12 is controlled by circuit breaker CB12 on BUS_B.",
        structured_value="CB12",
        provenance="Graph Traversal",
    )
    wrong_breaker_claim = Claim(
        claim_id="C03",
        statement="Feeder F12 is protected and controlled by vacuum circuit breaker CB13.",
        claim_type=ClaimType.FACT,
        evidence_ids=[evidence.evidence_id],
    )
    facts, inferences, rejected = ClaimVerifier.verify_candidate_claims([wrong_breaker_claim], [evidence])
    assert len(facts) == 0
    assert len(rejected) == 1
    assert rejected[0].verification_status == VerificationStatus.REJECTED
    assert "ungrounded equipment 'CB13'" in rejected[0].verification_notes.lower() or "statement" in rejected[0].verification_notes.lower()


def test_exact_verified_fact_passes():
    evidence = Evidence(
        evidence_id="EV_TOPO_RELAY",
        source_type=EvidenceSourceType.GRAPH,
        source_id="IN_MEMORY_TOPOLOGY",
        tool_name="TopologyTool",
        fact="RELAY_12 is configured as the primary protection relay for Feeder F12.",
        structured_value="RELAY_12",
        provenance="Graph Traversal",
    )
    valid_claim = Claim(
        claim_id="C04",
        statement="RELAY_12 is configured as the primary protection relay for Feeder F12.",
        claim_type=ClaimType.FACT,
        evidence_ids=[evidence.evidence_id],
    )
    facts, inferences, rejected = ClaimVerifier.verify_candidate_claims([valid_claim], [evidence])
    assert len(facts) == 1
    assert len(rejected) == 0
    assert facts[0].verification_status == VerificationStatus.VERIFIED
