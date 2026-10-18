"""Regression tests for verification boundaries using valid and mutated pairs."""
from dataclasses import replace
import pytest
from domain.claims.models import Claim, ClaimType, VerificationStatus as V
from domain.evidence.models import Evidence, EvidenceKind as K, EvidenceSourceType as S
from services.agent.claims import ClaimConstructor
from services.agent.verifier import ClaimVerifier
from services.agent.faithfulness import FaithfulnessVerifier
from services.agent.derived import DerivedQuantityCrossChecker
from services.comtrade.parser import ComtradeParser
from services.comtrade.analyzer import ComtradeSignalAnalyzer
from services.evaluation.physical_cases import scenarios, render_inputs, score, evaluate_physical


def evidence(phase="B", threshold=1800., current=4200.):
    return [Evidence(evidence_id="rms", kind=K.CHANNEL_RMS, source_type=S.COMTRADE,
                     source_id="new.DAT", tool_name="waveform", fact=f"Phase {phase} fault RMS current = {current} A.",
                     structured_value=current, unit="A", provenance="calculated", metadata={"phase": phase, "channel": "I"+phase}),
            Evidence(evidence_id="pickup", kind=K.OVERCURRENT_EXCEEDED, source_type=S.COMTRADE,
                     source_id="new.DAT", tool_name="waveform", fact="Configured pickup exceeded.",
                     structured_value=True, provenance="comparison", metadata={"fault_phase": phase, "pickup_threshold_a": threshold})]


@pytest.mark.parametrize("phase", list("ABC"))
@pytest.mark.parametrize("threshold", [900., 1800., 3500.])
def test_inference_is_recomputed_and_tracks_actual_measurements(phase, threshold):
    evs = evidence(phase, threshold)
    candidates = ClaimConstructor.construct_candidate_claims(evs, [])
    facts, infs, rejected = ClaimVerifier.verify_claims(candidates, evs)
    assert len(infs) == 1 and not rejected
    assert infs[0].inference_result == {"phase": phase, "fault_rms_a": 4200., "pickup_a": threshold}
    assert f"Phase {phase}" in infs[0].statement and f"{threshold:.2f} A" in infs[0].statement
    assert "does not establish" in infs[0].statement
    infs[0].statement = infs[0].statement.replace("met or exceeded", "did not exceed")
    assert not ClaimVerifier.verify_claims(candidates, evs)[1]


@pytest.mark.parametrize("mutation", ["result", "rule", "premise", "evidence", "preverified", "source"])
def test_inference_tampering_fails_closed(mutation):
    evs = evidence()
    cs = ClaimConstructor.construct_candidate_claims(evs, [])
    inference = next(c for c in cs if c.claim_type == ClaimType.INFERENCE)
    if mutation == "result": inference.inference_result["fault_rms_a"] = 9999
    if mutation == "rule": inference.inference_rule_id = "LOOKS_LEGITIMATE"
    if mutation == "premise": inference.premise_claim_ids = ["missing"]
    if mutation == "evidence": inference.evidence_ids = ["rms"]
    if mutation == "preverified":
        cs[0].statement = "The relay was destroyed."
        cs[0].verification_status = V.VERIFIED
    if mutation == "source": evs[1].source_id = "different.DAT"
    assert not ClaimVerifier.verify_claims(cs, evs)[1]


@pytest.mark.parametrize("statement", [
    "Phase B fault RMS current = 4200.0 A, and therefore the relay failed.",
    "Phase B fault RMS current was not 4200.0 A.",
    "Phase A fault RMS current = 4200.0 A.",
    "Phase B pre-fault RMS current = 4200.0 A.",
    "Phase B peak current = 4200.0 A.",
    "Phase B fault RMS current = 4200.0 V.",
])
def test_binding_polarity_role_and_extra_clause_mutants(statement):
    ev = evidence()[0]
    c = Claim(claim_id="c", statement=ev.fact, claim_type=ClaimType.FACT, evidence_ids=[ev.evidence_id])
    assert ClaimVerifier.verify_claims([c], [ev])[0]
    assert FaithfulnessVerifier.verify_faithfulness(c.statement, [c])[0]
    assert not FaithfulnessVerifier.verify_faithfulness(statement, [c])[0]
    c.statement = statement
    assert ClaimVerifier.verify_claims([c], [ev])[2]


def test_secondary_current_needs_explicit_cited_ratio():
    ev = evidence()[0]
    c = Claim(claim_id="c", statement="Channel IB secondary RMS current = 21 A.", claim_type=ClaimType.FACT, evidence_ids=["rms"])
    assert not DerivedQuantityCrossChecker.check_derived_claim(c, {"rms": ev})[0]
    ev.metadata["ct_ratio"] = 200
    assert DerivedQuantityCrossChecker.check_derived_claim(c, {"rms": ev})[0]
    ev.metadata["ct_ratio"] = 400
    assert not DerivedQuantityCrossChecker.check_derived_claim(c, {"rms": ev})[0]


@pytest.mark.parametrize("unit,scaling", [("A", "P"), ("kA", "P"), ("A", "S"), ("kA", "S")])
def test_physical_unit_and_ratio_invariance(unit, scaling):
    case = replace(scenarios("heldout")[1], unit=unit, scaling=scaling)
    cfg, dat = render_inputs(case)
    record = ComtradeParser.parse_dat(dat, ComtradeParser.parse_cfg(cfg))
    observed = ComtradeSignalAnalyzer.analyze_record(record, case.case_id, case.pickup_a)
    checks, error = score(case, observed)
    assert all(checks.values()) and error < .0001
    assert all(m.unit == "A" for m in observed.analog_measurements.values())
    assert record.normalization["MEAS_A"]["source_unit"] == unit


@pytest.mark.parametrize("mutation", ["nan", "missing_field", "duplicate_index", "backwards_time", "bad_bit", "extra_field"])
def test_malformed_dat_never_silently_skipped(mutation):
    cfg, dat = render_inputs(scenarios("dev")[1])
    lines = dat.splitlines()
    row = lines[4].split(",")
    if mutation == "nan": row[2] = "nan"
    if mutation == "missing_field": row.pop()
    if mutation == "duplicate_index": row[0] = "4"
    if mutation == "backwards_time": row[1] = "1"
    if mutation == "bad_bit": row[-1] = "2"
    if mutation == "extra_field": row.append("0")
    lines[4] = ",".join(row)
    with pytest.raises(ValueError):
        ComtradeParser.parse_dat("\n".join(lines), ComtradeParser.parse_cfg(cfg))


def test_even_one_missing_sample_is_incomplete():
    cfg, dat = render_inputs(scenarios("dev")[1])
    record = ComtradeParser.parse_dat("\n".join(dat.splitlines()[:-1]), ComtradeParser.parse_cfg(cfg))
    assert record.is_truncated


def test_disjoint_actual_input_families_and_oracle_sensitivity():
    import hashlib
    dev, held = scenarios("dev"), scenarios("heldout")
    assert {c.family for c in dev}.isdisjoint({c.family for c in held})
    hashes = lambda cases: {hashlib.sha256(render_inputs(c)[1].encode()).hexdigest() for c in cases}
    assert hashes(dev).isdisjoint(hashes(held))
    case = dev[1]
    cfg, dat = render_inputs(case)
    observed = ComtradeSignalAnalyzer.analyze_record(ComtradeParser.parse_dat(dat, ComtradeParser.parse_cfg(cfg)), case.case_id, case.pickup_a)
    assert all(score(case, observed)[0].values())
    assert not all(score(replace(case, amplitude_a=case.amplitude_a * 1.5), observed)[0].values())


@pytest.mark.asyncio
async def test_new_incident_reaches_full_workflow_without_hidden_labels():
    report = await evaluate_physical("heldout", scenarios("heldout")[:3])
    assert report["passed"] == 3
    assert len({r["dat_sha256"] for r in report["results"]}) == 3
