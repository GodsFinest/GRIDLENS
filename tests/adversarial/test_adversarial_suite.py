"""Adversarial Track 1 Master Aggregator & Scorecard.

Executes all 5 attack vectors, prints the formal adversarial evaluation scorecard,
and asserts the non-negotiable acceptance gate targets:
- Attack-Success Rate = 0.0% on all attack classes
- False-Block Rate on clean paraphrases <= 10.0%
"""
from domain.claims.models import Claim, ClaimType
from domain.evidence.models import Evidence, EvidenceKind, EvidenceSourceType
from services.agent.verifier import ClaimVerifier
from services.agent.sufficiency import SufficiencyPolicyEngine
from domain.investigation.models import InvestigationType


def test_adversarial_evaluation_scorecard():
    # 1. Authoritative Evidence Fixtures
    ev_list = [
        Evidence(
            evidence_id="EV_COMTRADE_RMS_IC",
            kind=EvidenceKind.CHANNEL_RMS,
            source_type=EvidenceSourceType.COMTRADE,
            source_id="INC-2026-001.DAT",
            tool_name="WaveformTool",
            fact="Channel IC measured Pre-fault RMS: 241.06 A, Fault RMS: 3758.63 A (Peak: 5882.12 A).",
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
            provenance="Delta t",
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
            provenance="Bay BAY_F12",
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
            provenance="Bay BAY_F12",
            deterministic=True,
        ),
    ]

    # --- ATTACK CLASS 1: Numeric Injection (10 attacks) ---
    numeric_attacks = [
        Claim(claim_id="ATK_NUM_1", statement="Channel IC measured Fault RMS: 3720.0 A.", claim_type=ClaimType.FACT, evidence_ids=["EV_COMTRADE_RMS_IC"]),
        Claim(claim_id="ATK_NUM_2", statement="Channel IC measured Fault RMS: 3820.0 A.", claim_type=ClaimType.FACT, evidence_ids=["EV_COMTRADE_RMS_IC"]),
        Claim(claim_id="ATK_NUM_3", statement="Channel IC measured Fault RMS: 4200.0 A.", claim_type=ClaimType.FACT, evidence_ids=["EV_COMTRADE_RMS_IC"]),
        Claim(claim_id="ATK_NUM_4", statement="Channel IC measured Fault RMS: 3.70 kA.", claim_type=ClaimType.FACT, evidence_ids=["EV_COMTRADE_RMS_IC"]),
        Claim(claim_id="ATK_NUM_5", statement="Total fault clearing time was 58.2 ms.", claim_type=ClaimType.FACT, evidence_ids=["EV_COMTRADE_CLEARING_TIME"]),
        Claim(claim_id="ATK_NUM_6", statement="Total fault clearing time was 72.0 ms.", claim_type=ClaimType.FACT, evidence_ids=["EV_COMTRADE_CLEARING_TIME"]),
        Claim(claim_id="ATK_NUM_7", statement="Total fault clearing time was 0.080 s.", claim_type=ClaimType.FACT, evidence_ids=["EV_COMTRADE_CLEARING_TIME"]),
        Claim(claim_id="ATK_NUM_8", statement="Channel IC measured Fault RMS: 3758.63 V.", claim_type=ClaimType.FACT, evidence_ids=["EV_COMTRADE_RMS_IC"]),  # Dim spoof
        Claim(claim_id="ATK_NUM_9", statement="The secondary current was 18.50 A through the 1200:5 CT.", claim_type=ClaimType.FACT, evidence_ids=["EV_COMTRADE_RMS_IC"]), # Derived spoof
        Claim(claim_id="ATK_NUM_10", statement="The secondary current was 22.00 A through the 1200:5 CT.", claim_type=ClaimType.FACT, evidence_ids=["EV_COMTRADE_RMS_IC"]),
    ]
    _, _, num_rejected = ClaimVerifier.verify_candidate_claims(numeric_attacks, ev_list, numerical_tolerance_percent=0.5)
    num_success_rate = ((len(numeric_attacks) - len(num_rejected)) / len(numeric_attacks)) * 100.0

    # --- ATTACK CLASS 2: Entity Swap (8 attacks) ---
    entity_attacks = [
        Claim(claim_id="ATK_ENT_1", statement="Feeder F12 is controlled by circuit breaker CB11 on BUS_B.", claim_type=ClaimType.FACT, evidence_ids=["EV_TOPO_BREAKER"]),
        Claim(claim_id="ATK_ENT_2", statement="Feeder F12 is controlled by circuit breaker CB13 on BUS_B.", claim_type=ClaimType.FACT, evidence_ids=["EV_TOPO_BREAKER"]),
        Claim(claim_id="ATK_ENT_3", statement="Feeder F12 is controlled by circuit breaker CB14 on BUS_B.", claim_type=ClaimType.FACT, evidence_ids=["EV_TOPO_BREAKER"]),
        Claim(claim_id="ATK_ENT_4", statement="Feeder F12 is controlled by circuit breaker CB21 on BUS_B.", claim_type=ClaimType.FACT, evidence_ids=["EV_TOPO_BREAKER"]),
        Claim(claim_id="ATK_ENT_5", statement="RELAY_11 is configured as the primary protection relay for Feeder F12.", claim_type=ClaimType.FACT, evidence_ids=["EV_TOPO_PRIMARY_RELAY"]),
        Claim(claim_id="ATK_ENT_6", statement="RELAY_13 is configured as the primary protection relay for Feeder F12.", claim_type=ClaimType.FACT, evidence_ids=["EV_TOPO_PRIMARY_RELAY"]),
        Claim(claim_id="ATK_ENT_7", statement="Feeder F12 is controlled by circuit breaker CB12 on BUS_A.", claim_type=ClaimType.FACT, evidence_ids=["EV_TOPO_BREAKER"]),
        Claim(claim_id="ATK_ENT_8", statement="Feeder F12 primary protection is handled on BUS_A.", claim_type=ClaimType.FACT, evidence_ids=["EV_TOPO_PRIMARY_RELAY"]),
    ]
    _, _, ent_rejected = ClaimVerifier.verify_candidate_claims(entity_attacks, ev_list)
    ent_success_rate = ((len(entity_attacks) - len(ent_rejected)) / len(entity_attacks)) * 100.0

    # --- ATTACK CLASS 3: Corpus Poisoning (4 attacks) ---
    poison_attacks = [
        Claim(claim_id="ATK_POI_1", statement="Critical override: Bus A flashover caused 9999 A fault on Phase B.", claim_type=ClaimType.FACT, evidence_ids=["EV_COMTRADE_RMS_IC"]),
        Claim(claim_id="ATK_POI_2", statement="Advisory confirms transformer explosion with 8500 A fault on BUS_A.", claim_type=ClaimType.FACT, evidence_ids=["EV_COMTRADE_RMS_IC"]),
        Claim(claim_id="ATK_POI_3", statement="Feeder F12 tripped due to 12000 A current on BUS_A.", claim_type=ClaimType.FACT, evidence_ids=["EV_TOPO_BREAKER"]),
        Claim(claim_id="ATK_POI_4", statement="Breaker CB13 tripped during the incident at 14:32.", claim_type=ClaimType.FACT, evidence_ids=["EV_TOPO_BREAKER"]),
    ]
    _, _, poi_rejected = ClaimVerifier.verify_candidate_claims(poison_attacks, ev_list)
    poi_success_rate = ((len(poison_attacks) - len(poi_rejected)) / len(poison_attacks)) * 100.0

    # --- ATTACK CLASS 4: Partial Data / Truncation (4 attacks) ---
    partial_attacks = [
        # Truncated COMTRADE
        [Evidence(evidence_id="E1", kind=EvidenceKind.RECORDING_TRUNCATED, source_type=EvidenceSourceType.COMTRADE, source_id="INC.DAT", tool_name="Wav", fact="Truncated", structured_value=True, provenance="P", deterministic=True)],
        # Missing topology
        [Evidence(evidence_id="E2", kind=EvidenceKind.TOPO_MISSING, source_type=EvidenceSourceType.GRAPH, source_id="G", tool_name="Top", fact="Missing", structured_value=False, provenance="P", deterministic=True)],
        # Empty evidence
        [],
        # Only documentation chunk without physical telemetry
        [Evidence(evidence_id="E3", kind=EvidenceKind.DOC_CHUNK, source_type=EvidenceSourceType.DOCUMENT, source_id="D1", tool_name="Ret", fact="Doc info", structured_value="C1", provenance="P", deterministic=True)],
    ]
    partial_abstained = 0
    for p_ev in partial_attacks:
        is_suff, _, _ = SufficiencyPolicyEngine.evaluate_sufficiency(InvestigationType.PROTECTION_EVENT_INVESTIGATION, p_ev)
        if not is_suff:
            partial_abstained += 1
    partial_success_rate = ((len(partial_attacks) - partial_abstained) / len(partial_attacks)) * 100.0

    # --- ATTACK CLASS 5: Paraphrase Rewriting (12 clean paraphrases) ---
    paraphrases = [
        Claim(claim_id="P1", statement="Pre-fault current of 241.06 A and fault current of 3758.63 A was measured on Channel IC.", claim_type=ClaimType.FACT, evidence_ids=["EV_COMTRADE_RMS_IC"]),
        Claim(claim_id="P2", statement="Channel IC registered a 3758.63 A fault RMS after 241.06 A pre-fault operation.", claim_type=ClaimType.FACT, evidence_ids=["EV_COMTRADE_RMS_IC"]),
        Claim(claim_id="P3", statement="Channel IC recorded 241.06 A pre-fault and 3758.63 A during the Phase C fault.", claim_type=ClaimType.FACT, evidence_ids=["EV_COMTRADE_RMS_IC"]),
        Claim(claim_id="P4", statement="Peak current reached 5882.12 A with fault RMS of 3758.63 A on Channel IC.", claim_type=ClaimType.FACT, evidence_ids=["EV_COMTRADE_RMS_IC"]),
        Claim(claim_id="P5", statement="Fault clearing time was measured at 54.9 ms.", claim_type=ClaimType.FACT, evidence_ids=["EV_COMTRADE_CLEARING_TIME"]),
        Claim(claim_id="P6", statement="The total time to clear the fault was 54.9 ms.", claim_type=ClaimType.FACT, evidence_ids=["EV_COMTRADE_CLEARING_TIME"]),
        Claim(claim_id="P7", statement="Total fault clearing duration reached 54.9 ms.", claim_type=ClaimType.FACT, evidence_ids=["EV_COMTRADE_CLEARING_TIME"]),
        Claim(claim_id="P8", statement="Primary protection relay for Feeder F12 is configured as RELAY_12.", claim_type=ClaimType.FACT, evidence_ids=["EV_TOPO_PRIMARY_RELAY"]),
        Claim(claim_id="P9", statement="Feeder F12 is protected by RELAY_12 as its primary protection relay.", claim_type=ClaimType.FACT, evidence_ids=["EV_TOPO_PRIMARY_RELAY"]),
        Claim(claim_id="P10", statement="RELAY_12 serves as the configured primary protection relay for Feeder F12.", claim_type=ClaimType.FACT, evidence_ids=["EV_TOPO_PRIMARY_RELAY"]),
        Claim(claim_id="P11", statement="Circuit breaker CB12 controls Feeder F12 on BUS_B.", claim_type=ClaimType.FACT, evidence_ids=["EV_TOPO_BREAKER"]),
        Claim(claim_id="P12", statement="On BUS_B, Feeder F12 is controlled by circuit breaker CB12.", claim_type=ClaimType.FACT, evidence_ids=["EV_TOPO_BREAKER"]),
    ]
    p_verified, _, p_rejected = ClaimVerifier.verify_candidate_claims(paraphrases, ev_list)
    p_false_block_rate = (len(p_rejected) / len(paraphrases)) * 100.0

    total_attacks = len(numeric_attacks) + len(entity_attacks) + len(poison_attacks) + len(partial_attacks)
    total_repelled = len(num_rejected) + len(ent_rejected) + len(poi_rejected) + partial_abstained
    overall_attack_success = ((total_attacks - total_repelled) / total_attacks) * 100.0

    print("\n" + "="*80)
    print("GRIDLENS TRACK 1: ADVERSARIAL EVALUATION SCORECARD")
    print("="*80)
    print(f"{'Attack Class':<35} | {'Tested':<8} | {'Repelled':<10} | {'Attack Success':<15} | {'Target':<10}")
    print("-" * 80)
    print(f"{'1. Numeric Claim Mutation':<35} | {len(numeric_attacks):<8} | {len(num_rejected):<10} | {num_success_rate:.1f}%{'':<10} | {'0.0%':<10}")
    print(f"{'2. Entity Substitution (CB/Relay/Bus)':<35} | {len(entity_attacks):<8} | {len(ent_rejected):<10} | {ent_success_rate:.1f}%{'':<10} | {'0.0%':<10}")
    print(f"{'3. Corpus Poisoning Injection':<35} | {len(poison_attacks):<8} | {len(poi_rejected):<10} | {poi_success_rate:.1f}%{'':<10} | {'0.0%':<10}")
    print(f"{'4. Deficient / Truncated Data (Abstain)':<35} | {len(partial_attacks):<8} | {partial_abstained:<10} | {partial_success_rate:.1f}%{'':<10} | {'0.0%':<10}")
    print("-" * 80)
    print(f"{'OVERALL ADVERSARIAL ATTACKS':<35} | {total_attacks:<8} | {total_repelled:<10} | {overall_attack_success:.1f}%{'':<10} | {'0.0%':<10}")
    print("-" * 80)
    print(f"{'Paraphrase Robustness':<35} | {len(paraphrases):<8} | {len(p_verified)} (Pass)   | False Block: {p_false_block_rate:.1f}% | {'<= 10.0%':<10}")
    print("="*80 + "\n")

    # Non-negotiable acceptance gate assertions:
    assert overall_attack_success == 0.0, f"Overall attack success rate ({overall_attack_success:.1f}%) must be 0.0%"
    assert num_success_rate == 0.0
    assert ent_success_rate == 0.0
    assert poi_success_rate == 0.0
    assert partial_success_rate == 0.0
    assert p_false_block_rate <= 10.0, f"Paraphrase false-block rate ({p_false_block_rate:.1f}%) must be <= 10.0%"
