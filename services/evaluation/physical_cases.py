"""Fresh physical-input evaluation, separate from curated query regressions.

Development: 50 Hz sinusoidal steps. Held-out family: 60 Hz, third-harmonic
steps. Both run through actual CFG/DAT files, WaveformTool and the full graph.
The oracle is the analytic generator specification, never a workflow input.
This tests these synthetic signal families, NOT clinical/field diagnostic accuracy.
"""
import asyncio
import hashlib
import json
import math
import random
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from domain.investigation.models import InvestigationRequest
from services.agent.graph import GridLensInvestigationWorkflow
from services.agent.llm_provider import MockLLMProvider
from services.tools.waveform_tool import WaveformTool


@dataclass(frozen=True)
class Scenario:
    case_id: str
    family: str
    phase: str
    amplitude_a: float
    load_a: float
    pickup_a: float
    frequency_hz: int
    harmonic: float
    unit: str
    scaling: str
    ratio: float
    truncated: bool
    onset_ms: float = 80.0
    open_ms: float = 320.0
    sample_rate: int = 6000

    @property
    def rms_oracle(self):
        return self.amplitude_a * math.sqrt(1 + self.harmonic**2)


def scenarios(split):
    if split not in {"dev", "heldout"}:
        raise ValueError("split must be dev or heldout")
    rng = random.Random(91872 if split == "dev" else 58201)
    return [Scenario(
        case_id=f"PHYS-{split.upper()}-{i:03d}", family="sine_50hz" if split == "dev" else "harmonic_60hz",
        phase="ABC"[i % 3], amplitude_a=rng.uniform(3500, 7000) if i % 4 else rng.uniform(1000, 1500),
        load_a=rng.uniform(100, 220), pickup_a=rng.uniform(2000, 3000),
        frequency_hz=50 if split == "dev" else 60, harmonic=0 if split == "dev" else rng.uniform(.05, .25),
        unit="A" if i % 2 else "kA", scaling="P" if i % 3 else "S",
        ratio=rng.choice([100., 200., 400.]), truncated=i % 5 == 0,
    ) for i in range(80 if split == "dev" else 40)]


def render_inputs(case):
    expected = int(.4 * case.sample_rate)
    count = int(.18 * case.sample_rate) if case.truncated else expected
    cfg = [f"GENERATED,{case.case_id},2013", "4,3A,1D"]
    for i, phase in enumerate("ABC", 1):
        cfg.append(f"{i},MEAS_{phase},{phase},,{case.unit},1,0,0,-100000,100000,{case.ratio},1,{case.scaling}")
    cfg += ["1,52A_BRK,,,1", str(case.frequency_hz), "1", f"{case.sample_rate},{expected}",
            "01/01/2026,00:00:00.000000", "01/01/2026,00:00:00.080000", "ASCII", "1"]
    rows = []
    divisor = (1000 if case.unit == "kA" else 1) * (case.ratio if case.scaling == "S" else 1)
    for i in range(count):
        t = i / case.sample_rate
        active = case.onset_ms <= t * 1000 < case.open_ms
        values = []
        for j, phase in enumerate("ABC"):
            amplitude = case.amplitude_a if active and phase == case.phase else case.load_a
            angle = 2 * math.pi * case.frequency_hz * t - j * 2 * math.pi / 3
            h3 = case.harmonic if active and phase == case.phase else 0
            value = math.sqrt(2) * amplitude * (math.sin(angle) + h3 * math.sin(3 * angle))
            values.append(f"{value/divisor:.12f}")
        rows.append(",".join([str(i+1), f"{t*1e6:.6f}", *values, str(int(t*1000 < case.open_ms))]))
    return "\n".join(cfg) + "\n", "\n".join(rows) + "\n"


class CapturingWaveformTool(WaveformTool):
    """Observe the normal tool result for scoring; never substitutes an oracle."""
    async def execute(self, *args, **kwargs):
        self.observed = await super().execute(*args, **kwargs)
        return self.observed


def score(case, observed):
    measurement = observed.analog_measurements.get(f"MEAS_{case.phase}")
    error = abs(measurement.fault_rms - case.rms_oracle) / case.rms_oracle if measurement else None
    edge_ok = (observed.breaker_open_time_ms is None if case.truncated else
               observed.breaker_open_time_ms is not None and abs(observed.breaker_open_time_ms - case.open_ms) <= 1000/case.sample_rate)
    onset_ok = observed.onset_time_ms is not None and case.onset_ms <= observed.onset_time_ms <= case.onset_ms + 1000/case.frequency_hz
    checks = {"rms_within_one_percent": error is not None and error <= .01,
              "phase": observed.fault_phase_detected == case.phase,
              "pickup": observed.pickup_exceeded == (case.rms_oracle >= case.pickup_a),
              "truncation": observed.is_truncated == case.truncated, "breaker_edge": edge_ok,
              "onset_within_one_cycle": onset_ok}
    return checks, error


async def evaluate_physical(split="dev", cases=None):
    selected = scenarios(split) if cases is None else cases
    rows = []
    with tempfile.TemporaryDirectory(prefix="gridlens-physical-") as directory:
        tool = CapturingWaveformTool(directory)
        workflow = GridLensInvestigationWorkflow(waveform_tool=tool, llm_provider=MockLLMProvider())
        for case in selected:
            cfg, dat = render_inputs(case)
            Path(directory, case.case_id + ".CFG").write_text(cfg, encoding="utf-8")
            Path(directory, case.case_id + ".DAT").write_text(dat, encoding="utf-8")
            # Only case-independent context and known relay pickup setting enter
            # the workflow. No expected current, phase, diagnosis, or timing.
            context = {"incident_id": case.case_id, "comtrade_file_id": case.case_id,
                       "feeder_id": "F12", "bay_id": "BAY_F12", "involved_ied_id": "IED_12",
                       "pickup_threshold_a": case.pickup_a, "events": []}
            result = await workflow.run_investigation(InvestigationRequest(
                investigation_id=case.case_id, incident_id=case.case_id,
                user_query="Investigate the feeder trip using waveform evidence.", target_equipment_id="F12"),
                incident_data=context)
            checks, error = score(case, tool.observed)
            checks["waveform_tool_executed"] = any(t.tool_invoked == "WaveformTool" for t in result.execution_trace)
            # Independently bind the displayed report measurement to the oracle.
            cited = next((c for c in result.verified_facts if c.evidence_ids == [f"EV_COMTRADE_RMS_MEAS_{case.phase}"]), None)
            checks["report_contains_measured_current"] = bool(cited and f"Fault RMS: {tool.observed.analog_measurements[f'MEAS_{case.phase}'].fault_rms} A" in cited.statement)
            rows.append({"case_id": case.case_id, "family": case.family, "specification": asdict(case),
                         "input_sha256": hashlib.sha256((cfg + dat).encode()).hexdigest(),
                         "dat_sha256": hashlib.sha256(dat.encode()).hexdigest(),
                         "oracle_rms_a": case.rms_oracle, "observed": tool.observed.model_dump(),
                         "relative_rms_error": error, "checks": checks, "passed": all(checks.values()),
                         "hypothesis": result.hypotheses[0].code if result.hypotheses else None,
                         "sufficiency": result.is_sufficient})
    return {"schema_version": 1, "split": split, "status": "completed", "cases": len(rows),
            "passed": sum(r["passed"] for r in rows), "families": sorted({c.family for c in selected}),
            "scope": "Synthetic waveform/tool/report correctness; fixed seeded topology, not diagnostic generalization or a live LLM benchmark.",
            "thresholds": {"relative_rms_error": .01, "onset_error": "at most one nominal cycle", "edge_error": "one sample"},
            "results": rows}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "heldout"], default="heldout")
    args = parser.parse_args()
    report = asyncio.run(evaluate_physical(args.split))
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] == report["cases"] else 1)
