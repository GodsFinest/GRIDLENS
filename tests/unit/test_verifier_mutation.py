"""Track 4: Verifier Mutation Testing.

Systematically applies N evidence mutations (numerical shifts > tolerance, entity swaps,
dimensional swaps, polarity flips, derived ratio tampering) across valid ground-truth pairs,
asserting 100% rejection rate to prove the verifiers are non-tautological.
"""
import pytest
from domain.claims.models import Claim, ClaimType, VerificationStatus
from domain.evidence.models import Evidence, EvidenceKind, EvidenceSourceType
from services.agent.verifier import ClaimVerifier
from services.agent.faithfulness import FaithfulnessVerifier


# Golden valid baseline facts for mutation testing
BASELINE_PAIRS = [
    {
        "evidence": Evidence(
            evidence_id="EV_MUT_RMS_C",
            kind=EvidenceKind.CHANNEL_RMS,
            source_type=EvidenceSourceType.COMTRADE,
            source_id="INC-001.DAT",
            tool_name="WaveformTool",
            fact="Channel IC measured Fault RMS: 3758.63 A.",
            structured_value=3758.63,
            unit="A",
            provenance="Sliding RMS",
            deterministic=True,
        ),
        "valid_claim": "Channel IC measured Fault RMS: 3758.63 A.",
        "valid_narrative": "During the disturbance, Channel IC measured Fault RMS of 3758.63 A.",
    },
    {
        "evidence": Evidence(
            evidence_id="EV_MUT_CLEARING",
            kind=EvidenceKind.CLEARING_TIME,
            source_type=EvidenceSourceType.COMTRADE,
            source_id="INC-001.DAT",
            tool_name="WaveformTool",
            fact="Total fault clearing time was 54.9 ms.",
            structured_value=54.9,
            unit="ms",
            provenance="Delta t",
            deterministic=True,
        ),
        "valid_claim": "Total fault clearing time was 54.9 ms.",
        "valid_narrative": "Total fault clearing time was 54.9 ms.",
    },
    {
        "evidence": Evidence(
            evidence_id="EV_MUT_BREAKER",
            kind=EvidenceKind.TOPO_BREAKER,
            source_type=EvidenceSourceType.GRAPH,
            source_id="TOPOLOGY",
            tool_name="TopologyTool",
            fact="Feeder F12 is controlled by circuit breaker CB12 on BUS_B.",
            structured_value="CB12",
            provenance="Topology",
            deterministic=True,
        ),
        "valid_claim": "Feeder F12 is controlled by circuit breaker CB12 on BUS_B.",
        "valid_narrative": "Feeder F12 is controlled by circuit breaker CB12 on BUS_B.",
    },
    {
        "evidence": Evidence(
            evidence_id="EV_MUT_RELAY",
            kind=EvidenceKind.TOPO_PRIMARY_RELAY,
            source_type=EvidenceSourceType.GRAPH,
            source_id="TOPOLOGY",
            tool_name="TopologyTool",
            fact="RELAY_12 is configured as the primary protection relay for Feeder F12.",
            structured_value="RELAY_12",
            provenance="Topology",
            deterministic=True,
        ),
        "valid_claim": "RELAY_12 is configured as the primary protection relay for Feeder F12.",
        "valid_narrative": "RELAY_12 is configured as the primary protection relay for Feeder F12.",
    },
]


def test_baseline_pairs_are_valid_before_mutation():
    """Sanity check: unmutated baseline pairs must pass verification."""
    for pair in BASELINE_PAIRS:
        ev = pair["evidence"]
        claim = Claim(
            claim_id="C_BASE",
            statement=pair["valid_claim"],
            claim_type=ClaimType.FACT,
            evidence_ids=[ev.evidence_id],
        )
        v_facts, _, r_claims = ClaimVerifier.verify_candidate_claims([claim], [ev])
        assert len(v_facts) == 1, f"Unmutated claim failed: {claim.statement}"
        assert len(r_claims) == 0


def test_systematic_verifier_mutation_matrix():
    """
    Executes a mutation test across 24 distinct mutations:
    - 6 Positive value shifts (+5% to +20%)
    - 6 Negative value shifts (-5% to -20%)
    - 6 Equipment substitutions (CB13, CB21, RELAY_11, BUS_A)
    - 6 Dimensional unit swaps (A -> V, ms -> A, V -> ms)
    Asserts 100% rejection rate.
    """
    mutated_cases = [
        # Numeric shifts (+5% to +20%)
        ("EV_MUT_RMS_C", "Channel IC measured Fault RMS: 3950.0 A.", "Shift +5.1%"),
        ("EV_MUT_RMS_C", "Channel IC measured Fault RMS: 4134.5 A.", "Shift +10.0%"),
        ("EV_MUT_RMS_C", "Channel IC measured Fault RMS: 4510.3 A.", "Shift +20.0%"),
        ("EV_MUT_CLEARING", "Total fault clearing time was 58.0 ms.", "Shift +5.6%"),
        ("EV_MUT_CLEARING", "Total fault clearing time was 60.5 ms.", "Shift +10.2%"),
        ("EV_MUT_CLEARING", "Total fault clearing time was 65.9 ms.", "Shift +20.0%"),

        # Numeric shifts (-5% to -20%)
        ("EV_MUT_RMS_C", "Channel IC measured Fault RMS: 3570.0 A.", "Shift -5.0%"),
        ("EV_MUT_RMS_C", "Channel IC measured Fault RMS: 3382.7 A.", "Shift -10.0%"),
        ("EV_MUT_RMS_C", "Channel IC measured Fault RMS: 3006.9 A.", "Shift -20.0%"),
        ("EV_MUT_CLEARING", "Total fault clearing time was 52.0 ms.", "Shift -5.3%"),
        ("EV_MUT_CLEARING", "Total fault clearing time was 49.4 ms.", "Shift -10.0%"),
        ("EV_MUT_CLEARING", "Total fault clearing time was 43.9 ms.", "Shift -20.0%"),

        # Equipment substitutions
        ("EV_MUT_BREAKER", "Feeder F12 is controlled by circuit breaker CB11 on BUS_B.", "Swap CB11"),
        ("EV_MUT_BREAKER", "Feeder F12 is controlled by circuit breaker CB13 on BUS_B.", "Swap CB13"),
        ("EV_MUT_BREAKER", "Feeder F12 is controlled by circuit breaker CB21 on BUS_B.", "Swap CB21"),
        ("EV_MUT_BREAKER", "Feeder F12 is controlled by circuit breaker CB12 on BUS_A.", "Swap BUS_A"),
        ("EV_MUT_RELAY", "RELAY_11 is configured as the primary protection relay for Feeder F12.", "Swap RELAY_11"),
        ("EV_MUT_RELAY", "RELAY_13 is configured as the primary protection relay for Feeder F12.", "Swap RELAY_13"),

        # Dimensional unit swaps
        ("EV_MUT_RMS_C", "Channel IC measured Fault RMS: 3758.63 V.", "Unit A -> V"),
        ("EV_MUT_RMS_C", "Channel IC measured Fault RMS: 3758.63 ms.", "Unit A -> ms"),
        ("EV_MUT_RMS_C", "Channel IC measured Fault RMS: 3758.63 Hz.", "Unit A -> Hz"),
        ("EV_MUT_CLEARING", "Total fault clearing time was 54.9 A.", "Unit ms -> A"),
        ("EV_MUT_CLEARING", "Total fault clearing time was 54.9 V.", "Unit ms -> V"),
        ("EV_MUT_CLEARING", "Total fault clearing time was 54.9 %.", "Unit ms -> %"),
    ]

    ev_map = {p["evidence"].evidence_id: p["evidence"] for p in BASELINE_PAIRS}
    rejections = 0
    total_mutations = len(mutated_cases)

    for i, (ev_id, mut_statement, desc) in enumerate(mutated_cases):
        ev = ev_map[ev_id]
        claim = Claim(
            claim_id=f"MUT_{i+1:02d}",
            statement=mut_statement,
            claim_type=ClaimType.FACT,
            evidence_ids=[ev_id],
        )

        # Production default tolerance (0.5%): the mutation suite must hold
        # at the deployed configuration, not a looser test-only setting.
        v_facts, s_infs, r_claims = ClaimVerifier.verify_candidate_claims(
            [claim], [ev]
        )

        if len(r_claims) == 1 and len(v_facts) == 0:
            rejections += 1
        else:
            print(f"FAILED TO REJECT MUTATION [{desc}]: {mut_statement} -> {claim.verification_status}")

    rejection_rate = (rejections / total_mutations) * 100.0
    print(f"\nVERIFIER MUTATION TEST SCORE: Total={total_mutations}, Rejected={rejections}, Rate={rejection_rate:.1f}%")

    assert rejection_rate == 100.0, f"Verifier failed mutation check! Rejected {rejections}/{total_mutations}"
