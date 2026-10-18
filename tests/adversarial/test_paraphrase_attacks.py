"""Adversarial Track 1: Paraphrase Attacks.

Tests semantically identical but vocabulary-varied LLM rewrites of factual claims.
Target: False-Block Rate <= 10% (at least 90% of genuine paraphrases accepted).
"""
import pytest
from domain.claims.models import Claim, ClaimType, VerificationStatus
from domain.evidence.models import Evidence, EvidenceKind, EvidenceSourceType
from services.agent.verifier import ClaimVerifier


@pytest.fixture
def base_evidence():
    return [
        Evidence(
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
    ]


def test_clean_paraphrase_acceptance_rate(base_evidence):
    """Measures false-block rate across 12 semantically identical paraphrases."""
    paraphrase_claims = [
        # Waveform IC paraphrases (cites EV_COMTRADE_RMS_IC)
        Claim(
            claim_id="P_IC_1",
            statement="Pre-fault current of 241.06 A and fault current of 3758.63 A was measured on Channel IC.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_COMTRADE_RMS_IC"],
        ),
        Claim(
            claim_id="P_IC_2",
            statement="Channel IC registered a 3758.63 A fault RMS after 241.06 A pre-fault operation.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_COMTRADE_RMS_IC"],
        ),
        Claim(
            claim_id="P_IC_3",
            statement="Channel IC recorded 241.06 A pre-fault and 3758.63 A during the Phase C fault.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_COMTRADE_RMS_IC"],
        ),
        Claim(
            claim_id="P_IC_4",
            statement="Peak current reached 5882.12 A with fault RMS of 3758.63 A on Channel IC.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_COMTRADE_RMS_IC"],
        ),
        # Clearing time paraphrases (cites EV_COMTRADE_CLEARING_TIME)
        Claim(
            claim_id="P_TIME_1",
            statement="Fault clearing time was measured at 54.9 ms.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_COMTRADE_CLEARING_TIME"],
        ),
        Claim(
            claim_id="P_TIME_2",
            statement="The total time to clear the fault was 54.9 ms.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_COMTRADE_CLEARING_TIME"],
        ),
        Claim(
            claim_id="P_TIME_3",
            statement="Total fault clearing duration reached 54.9 ms.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_COMTRADE_CLEARING_TIME"],
        ),
        # Primary relay paraphrases (cites EV_TOPO_PRIMARY_RELAY)
        Claim(
            claim_id="P_RELAY_1",
            statement="Primary protection relay for Feeder F12 is configured as RELAY_12.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_TOPO_PRIMARY_RELAY"],
        ),
        Claim(
            claim_id="P_RELAY_2",
            statement="Feeder F12 is protected by RELAY_12 as its primary protection relay.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_TOPO_PRIMARY_RELAY"],
        ),
        Claim(
            claim_id="P_RELAY_3",
            statement="RELAY_12 serves as the configured primary protection relay for Feeder F12.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_TOPO_PRIMARY_RELAY"],
        ),
        # Breaker paraphrases (cites EV_TOPO_BREAKER)
        Claim(
            claim_id="P_BRK_1",
            statement="Circuit breaker CB12 controls Feeder F12 on BUS_B.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_TOPO_BREAKER"],
        ),
        Claim(
            claim_id="P_BRK_2",
            statement="On BUS_B, Feeder F12 is controlled by circuit breaker CB12.",
            claim_type=ClaimType.FACT,
            evidence_ids=["EV_TOPO_BREAKER"],
        ),
    ]

    total = len(paraphrase_claims)
    v_facts, s_infs, r_claims = ClaimVerifier.verify_candidate_claims(paraphrase_claims, base_evidence)

    accepted = len(v_facts)
    false_blocks = len(r_claims)
    false_block_rate = (false_blocks / total) * 100.0

    print(f"\nPARAPHRASE ATTACK RESULTS: Total={total}, Accepted={accepted}, FalseBlocks={false_blocks}, Rate={false_block_rate:.1f}%")
    if r_claims:
        for rc in r_claims:
            print(f"  False Block: '{rc.statement}' -> {rc.verification_notes}")

    assert false_block_rate <= 10.0, f"False-block rate ({false_block_rate:.1f}%) must be <= 10.0%"
    assert accepted >= 11, f"Expected at least 11 of 12 clean paraphrases accepted, got {accepted}"
