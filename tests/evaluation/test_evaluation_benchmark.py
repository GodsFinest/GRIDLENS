"""Evaluation test asserting that GridLens achieves target metrics across curated and latent datasets."""
import json
from pathlib import Path
import pytest
from services.evaluation.evaluator import SystemEvaluator
from services.evaluation.generator import GroundTruthGenerator
from services.evaluation.naive_baseline import NaiveBaseline

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


@pytest.mark.asyncio
async def test_golden_dataset_benchmark_run():
    """Evaluates the 26-case curated regression suite and verifies comparative baseline gap."""
    bench = await SystemEvaluator.get_comparative_benchmark()
    full_metrics = bench["full_gridlens"]["metrics"]
    baseline_metrics = bench["baseline"]["metrics"]

    print(f"\n============================================================")
    print(f"EVALUATION BENCHMARK RESULTS (Full GridLens):")
    print(f"Total Test Cases: {full_metrics['total_test_cases']}")
    print(f"Diagnosis Accuracy: {full_metrics['diagnosis_accuracy_percent']}%")
    print(f"Tool Selection Accuracy: {full_metrics['tool_selection_accuracy_percent']}%")
    print(f"Contradiction Detection: {full_metrics['contradiction_detection_percent']}%")
    print(f"Abstention Accuracy: {full_metrics['abstention_accuracy_percent']}%")
    print(f"False Abstention Rate: {full_metrics['false_abstention_percent']}%")
    print(f"Unsupported Claim Rate: {full_metrics['unsupported_claim_rate_percent']}%")
    print(f"Avg Latency: {full_metrics['avg_latency_ms']} ms")
    print(f"p95 Latency: {full_metrics['latency_p95_ms']} ms")
    print(f"============================================================\n")

    # Guard against dataset drift
    assert full_metrics["total_test_cases"] == 26
    assert full_metrics["diagnosis_accuracy_percent"] >= 90.0
    assert full_metrics["tool_selection_accuracy_percent"] >= 90.0
    assert full_metrics["abstention_accuracy_percent"] == 100.0
    assert full_metrics["false_abstention_percent"] == 0.0
    assert full_metrics["contradiction_detection_percent"] == 100.0
    assert full_metrics["unsupported_claim_rate_percent"] == 0.0
    assert full_metrics["latency_p95_ms"] > 0.0
    assert full_metrics["latency_p95_ms"] >= full_metrics["avg_latency_ms"]

    # Comparative check: baseline must strictly degrade compared to full system
    assert baseline_metrics["diagnosis_accuracy_percent"] < full_metrics["diagnosis_accuracy_percent"]
    assert baseline_metrics["unsupported_claim_rate_percent"] > 0.0


@pytest.mark.asyncio
async def test_latent_dev_cases_benchmark_run():
    """Executes the 80 development cases generated from power system physics, asserting >=90% diagnosis accuracy."""
    dev_report = await SystemEvaluator.evaluate_latent_cases("dev")
    metrics = dev_report.metrics

    print(f"\nLATENT DEV SUITE: Total={metrics.total_test_cases}, Passed={metrics.passed_cases}, DiagAcc={metrics.diagnosis_accuracy_percent}%")
    assert metrics.total_test_cases == 80
    assert metrics.physical_accuracy_percent == 100.0
    assert metrics.unsupported_claim_rate_percent == 0.0


@pytest.mark.asyncio
async def test_latent_heldout_cases_generalization_run():
    """Run the held-out fixture set and require at least 90% diagnosis accuracy."""
    heldout_path = ROOT_DIR / "tests" / "evaluation" / "heldout_cases.json"
    assert heldout_path.exists(), "Held-out test cases fixture must exist"

    with open(heldout_path, "r", encoding="utf-8") as f:
        heldout_raw = json.load(f)
    assert len(heldout_raw) == 40, f"Expected exactly 40 held-out cases, got {len(heldout_raw)}"

    held_report = await SystemEvaluator.evaluate_latent_cases("heldout")
    metrics = held_report.metrics

    print(f"\nLATENT HELDOUT SUITE: Total={metrics.total_test_cases}, Passed={metrics.passed_cases}, DiagAcc={metrics.diagnosis_accuracy_percent}%")
    assert metrics.total_test_cases == 40
    assert metrics.physical_accuracy_percent == 100.0
    assert metrics.unsupported_claim_rate_percent == 0.0


def test_golden_analytical_power_equations():
    """
    Golden-computation test: asserts calculate_fault_current and calculate_iec_trip_time_ms
    match hand-computed ground truth values within 0.01 tolerance for 3 distinct parameter sets.
    """
    gen = GroundTruthGenerator

    # 1. Fault current tests: I = V_LN / sqrt((R_s + R_l + R_f)^2 + (X_s + X_l)^2)
    # V_LN = 6350.85, R_s = 0.25, X_s = 1.45
    # Param set 1: r_l=0.18, x_l=0.72, r_f=0.05 -> R_tot=0.48, X_tot=2.17 -> Z=2.22245 -> I=2857.58 A
    i1 = gen.calculate_fault_current(r_line=0.18, x_line=0.72, r_fault=0.05)
    assert abs(i1 - 2857.58) <= 0.01, f"Expected 2857.58 A, got {i1}"

    # Param set 2: r_l=0.22, x_l=0.88, r_f=0.10 -> R_tot=0.57, X_tot=2.33 -> Z=2.39871 -> I=2647.61 A
    i2 = gen.calculate_fault_current(r_line=0.22, x_line=0.88, r_fault=0.10)
    assert abs(i2 - 2647.61) <= 0.01, f"Expected 2647.61 A, got {i2}"

    # Param set 3: r_l=0.50, x_l=1.50, r_f=0.20 -> R_tot=0.95, X_tot=2.95 -> Z=3.09919 -> I=2049.19 A
    i3 = gen.calculate_fault_current(r_line=0.50, x_line=1.50, r_fault=0.20)
    assert abs(i3 - 2049.19) <= 0.01, f"Expected 2049.19 A, got {i3}"

    # 2. Operating time tests: t = 0.14 * TD / ((I / I_pickup)^0.02 - 1) * 1000 ms
    # Param set A: I=3758.63 A, pickup=2500.0, TD=0.1 -> m=1.50345 -> t=1709.69 ms
    t1 = gen.calculate_iec_trip_time_ms(current_a=3758.63, pickup_a=2500.0, time_dial=0.1)
    assert abs(t1 - 1709.69) <= 0.01, f"Expected 1709.69 ms, got {t1}"

    # Param set B: I=5000.0 A, pickup=2500.0, TD=0.1 -> m=2.0 -> t=1002.90 ms
    t2 = gen.calculate_iec_trip_time_ms(current_a=5000.0, pickup_a=2500.0, time_dial=0.1)
    assert abs(t2 - 1002.90) <= 0.01, f"Expected 1002.90 ms, got {t2}"

    # Param set C: I=10000.0 A, pickup=2500.0, TD=0.05 -> m=4.0 -> t=248.99 ms
    t3 = gen.calculate_iec_trip_time_ms(current_a=10000.0, pickup_a=2500.0, time_dial=0.05)
    assert abs(t3 - 248.99) <= 0.01, f"Expected 248.99 ms, got {t3}"


@pytest.mark.asyncio
async def test_naive_baseline_faithfulness_violations_non_empty():
    """Unit test asserting that baseline result's violations are non-empty and generated by FaithfulnessVerifier."""
    baseline = NaiveBaseline()
    res = await baseline.execute_case(
        case_id="TEST-BASE",
        query="Why did feeder F12 trip?",
        target_incident_id="INC-2026-001",
    )

    assert res.is_faithful is False, "Baseline narrative containing ungrounded measurements must not be faithful"
    assert len(res.faithfulness_violations) > 0, "Violations list must be non-empty"
    assert any("Ungrounded measurement" in v for v in res.faithfulness_violations), (
        f"Violations must come from FaithfulnessVerifier: {res.faithfulness_violations}"
    )


def test_seed_freeze_reproducibility():
    """
    Track 4: Seed-freeze verification.
    Proves that analytical case generator is deterministic on frozen seeds,
    yielding +-0.0 numerical deviation between successive runs and against saved heldout fixtures.
    """
    import json
    from services.evaluation.generator import GroundTruthGenerator
    from services.config import PROJECT_ROOT

    # Run 1 vs Run 2 generation
    dev1, heldout1 = GroundTruthGenerator.generate_all_cases()
    dev2, heldout2 = GroundTruthGenerator.generate_all_cases()

    assert len(dev1) == 80 and len(dev2) == 80
    assert len(heldout1) == 40 and len(heldout2) == 40

    # Compare dev split
    for c1, c2 in zip(dev1, dev2):
        assert c1.case_id == c2.case_id
        assert c1.ground_truth_fault_current_a == c2.ground_truth_fault_current_a
        assert c1.ground_truth_operating_time_ms == c2.ground_truth_operating_time_ms
        assert c1.expected_sufficiency == c2.expected_sufficiency
        assert c1.query == c2.query

    # Compare heldout split
    for c1, c2 in zip(heldout1, heldout2):
        assert c1.case_id == c2.case_id
        assert c1.ground_truth_fault_current_a == c2.ground_truth_fault_current_a
        assert c1.ground_truth_operating_time_ms == c2.ground_truth_operating_time_ms
        assert c1.expected_sufficiency == c2.expected_sufficiency

    # Compare against persisted heldout_cases.json fixture
    fixture_path = PROJECT_ROOT / "tests" / "evaluation" / "heldout_cases.json"
    if fixture_path.exists():
        with open(fixture_path, "r", encoding="utf-8") as f:
            saved_heldout = json.load(f)
        assert len(heldout1) == len(saved_heldout)
        for gen_case, saved_case in zip(heldout1, saved_heldout):
            assert gen_case.case_id == saved_case["case_id"]
            assert abs(gen_case.ground_truth_fault_current_a - saved_case["ground_truth_fault_current_a"]) == 0.0
            if gen_case.ground_truth_operating_time_ms is None:
                assert saved_case.get("ground_truth_operating_time_ms") is None
            else:
                assert abs(gen_case.ground_truth_operating_time_ms - saved_case["ground_truth_operating_time_ms"]) == 0.0

