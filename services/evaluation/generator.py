"""Latent Ground Truth Generator computing analytical power system test cases."""
import json
import math
import os
from pathlib import Path
from typing import List, Optional, Tuple
from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
EVAL_DIR = ROOT_DIR / "tests" / "evaluation"


class LatentTestCase(BaseModel):
    case_id: str
    failure_mode: str
    query: str
    target_incident_id: str
    target_feeder_id: str
    expected_investigation_type: str
    expected_top_hypothesis_code: str
    expected_sufficiency: bool
    expected_tool_calls: List[str]
    expected_fact_keywords: List[str]
    ground_truth_fault_current_a: float
    ground_truth_fault_phase: str
    ground_truth_operating_time_ms: Optional[float] = None
    ground_truth_clearing_time_ms: Optional[float] = None
    is_negative_case: bool = False
    notes: str = ""


class GroundTruthGenerator:
    """
    Generates parameterised protection cases programmatically from power systems equations:
      - I_fault = V_LN / sqrt((R_s + R_line + R_fault)^2 + (X_s + X_line)^2)
      - t_op = (0.14 * time_dial) / ((I / I_pickup)^0.02 - 1)   [IEC Normal Inverse]
      - t_clear = t_op + t_mech
    """

    V_LN = 6350.85  # 11 kV / sqrt(3)
    R_SOURCE = 0.25
    X_SOURCE = 1.45

    @classmethod
    def calculate_iec_trip_time_ms(cls, current_a: float, pickup_a: float = 2500.0, time_dial: float = 0.1) -> float:
        """Calculates operating time in milliseconds using IEC 60255 Normal Inverse curve."""
        if current_a <= pickup_a:
            return 10000.0
        m = current_a / pickup_a
        t_sec = (0.14 * time_dial) / (math.pow(m, 0.02) - 1.0)
        return round(t_sec * 1000.0, 2)

    @classmethod
    def calculate_fault_current(cls, r_line: float, x_line: float, r_fault: float) -> float:
        """Calculates physical RMS symmetrical fault current in Amperes."""
        r_total = cls.R_SOURCE + r_line + r_fault
        x_total = cls.X_SOURCE + x_line
        z_total = math.sqrt(r_total**2 + x_total**2)
        return round(cls.V_LN / z_total, 2)

    @classmethod
    def generate_all_cases(cls) -> Tuple[List[LatentTestCase], List[LatentTestCase]]:
        """Generates 80 development cases and 40 held-out cases.

        The held-out split reuses the query templates (the template pool is 25
        queries, exhausted by dev) but samples a disjoint fault-resistance
        perturbation grid, so every formula-derived fault current is absent
        from dev. It is a disjoint-parameter resample, not a test of unseen
        query templates. Scenario-stipulated modes (QA, abstention,
        misoperation constants) reuse their constants by construction.
        """
        dev_cases: List[LatentTestCase] = []
        heldout_cases: List[LatentTestCase] = []

        total_target_dev = 80
        # Parameter variations: line lengths, fault resistances
        variations = [
            # 1. Genuine Phase C Overcurrent (INC-2026-001)
            {
                "mode": "GENUINE_PHASE_C_OVERCURRENT",
                "incident_id": "INC-2026-001",
                "feeder": "F12",
                "type": "PROTECTION_EVENT_INVESTIGATION",
                "hyp": "H1",
                "suff": True,
                "phase": "C",
                "tools": ["TopologyTool", "WaveformTool", "PhysicsTool", "ValidationTool", "SOETool", "RetrievalTool", "HistoryTool"],
                "r_line": 0.18, "x_line": 0.72, "r_fault": 0.05,
                "queries": [
                    "Why did feeder F12 trip at 14:32?",
                    "Investigate the overcurrent trip on bay F12.",
                    "Determine root cause for incident INC-2026-001.",
                    "Explain the breaker operation on feeder F12.",
                ],
            },
            # 2. Deceptive Channel Mapping Inversion (INC-2026-002)
            {
                "mode": "CT_PHASE_INVERSION",
                "incident_id": "INC-2026-002",
                "feeder": "F12",
                "type": "PROTECTION_EVENT_INVESTIGATION",
                "hyp": "H3",
                "suff": True,
                "phase": "C",
                "tools": ["TopologyTool", "WaveformTool", "PhysicsTool", "ValidationTool", "SOETool", "RetrievalTool", "HistoryTool"],
                "r_line": 0.22, "x_line": 0.88, "r_fault": 0.10,
                "queries": [
                    "Why did relay report Phase A trip when waveform surge was Phase C in INC-2026-002?",
                    "Investigate discrepancy between relay event and COMTRADE in Incident B.",
                    "Determine cause of conflicting phase evidence on feeder F12.",
                    "Validate CT secondary channel mapping consistency for bay F12.",
                ],
            },
            # 3. Truncated Oscillography / Insufficient Evidence (INC-2026-003)
            {
                "mode": "TRUNCATED_RECORDING_ABSTENTION",
                "incident_id": "INC-2026-003",
                "feeder": "F13",
                "type": "PROTECTION_EVENT_INVESTIGATION",
                "hyp": "H6",
                "suff": False,
                "phase": "C",
                "tools": ["TopologyTool", "WaveformTool", "PhysicsTool", "ValidationTool", "SOETool", "RetrievalTool", "HistoryTool"],
                "r_line": 0.35, "x_line": 1.20, "r_fault": 0.20,
                "queries": [
                    "Why did feeder F13 trip in incident INC-2026-003?",
                    "Diagnose feeder F13 trip event at 09:15.",
                    "Investigate truncated oscillography record for incident INC-2026-003.",
                ],
            },
            # 4. Unresolvable Cross-Source Discrepancy (INC-2026-004)
            {
                "mode": "UNRESOLVABLE_TELEMETRY_CONTRADICTION",
                "incident_id": "INC-2026-004",
                "feeder": "F12",
                "type": "PROTECTION_EVENT_INVESTIGATION",
                "hyp": "H6",
                "suff": False,
                "phase": "None",
                "tools": ["TopologyTool", "WaveformTool", "PhysicsTool", "ValidationTool", "SOETool", "RetrievalTool", "HistoryTool"],
                "r_line": 0.0, "x_line": 0.0, "r_fault": 100.0,  # Normal load (no fault)
                "queries": [
                    "Why did relay 12 assert Phase A trip when waveform showed normal load in INC-2026-004?",
                    "Investigate conflicting telemetry disturbance on feeder F12.",
                    "Explain contradictory relay target flag and oscillography in INC-2026-004.",
                ],
            },
            # 5. Settings Misoperation on Load Surge (INC-2026-005)
            {
                "mode": "SETTINGS_MISOPERATION",
                "incident_id": "INC-2026-005",
                "feeder": "F12",
                "type": "PROTECTION_EVENT_INVESTIGATION",
                "hyp": "H2",  # Corrected to H2: Protection Setting Misoperation
                "suff": True,
                "phase": "A",
                "tools": ["TopologyTool", "WaveformTool", "PhysicsTool", "ValidationTool", "SOETool", "RetrievalTool", "HistoryTool"],
                "r_line": 0.10, "x_line": 0.30, "r_fault": 11.0,
                "queries": [
                    "Why did feeder F12 trip on load inrush in incident INC-2026-005?",
                    "Investigate spurious trip on feeder F12 under 550A load.",
                    "Did relay pickup threshold violate feeder continuous rating in INC-2026-005?",
                ],
            },
            # 6. Topology & Documentation Inquiries
            {
                "mode": "TOPOLOGY_INQUIRY",
                "incident_id": "INC-2026-001",
                "feeder": "F12",
                "type": "TOPOLOGY_INQUIRY",
                "hyp": "H1",
                "suff": True,
                "phase": "C",
                "tools": ["TopologyTool"],
                "r_line": 0.0, "x_line": 0.0, "r_fault": 0.0,
                "queries": [
                    "Which circuit breaker protects feeder F12?",
                    "Which relay protects feeder F12?",
                    "What breaker is associated with feeder F13?",
                    "What sensors monitor feeder F12?",
                ],
            },
            {
                "mode": "DOCUMENTATION_QA",
                "incident_id": "INC-2026-001",
                "feeder": "F12",
                "type": "DOCUMENTATION_QA",
                "hyp": "H1",
                "suff": True,
                "phase": "C",
                "tools": ["RetrievalTool"],
                "r_line": 0.0, "x_line": 0.0, "r_fault": 0.0,
                "queries": [
                    "What does ANSI 51 mean in power system protection?",
                    "Explain the operating principle of inverse time overcurrent relays.",
                    "What is the standard clearing time range for distribution vacuum circuit breakers?",
                    "Define ANSI 50 instantaneous overcurrent protection.",
                ],
            },
        ]

        case_idx = 1
        for i in range(120):
            var = variations[i % len(variations)]
            q_list = var["queries"]
            query = q_list[(i // len(variations)) % len(q_list)]

            # Compute analytical parameters
            if var["mode"] in ["TOPOLOGY_INQUIRY", "DOCUMENTATION_QA"]:
                # No fault physics in these modes: zeroed ground truth by construction.
                i_fault = 0.0
                t_op = 0.0
                t_clear = 0.0
            elif var["mode"] == "UNRESOLVABLE_TELEMETRY_CONTRADICTION":
                # Scenario stipulation (not formula-derived): normal 240 A load
                # with relay/waveform disagreement; no meaningful trip time.
                i_fault = 240.0
                t_op = None
                t_clear = None
            elif var["mode"] == "TRUNCATED_RECORDING_ABSTENTION":
                # Scenario stipulation (not formula-derived): transient interrupted
                # mid-recording; clearance unobservable by construction.
                i_fault = 2900.0
                t_op = 15.0
                t_clear = None  # Truncated before clearance
            elif var["mode"] == "SETTINGS_MISOPERATION":
                # Scenario stipulation anchored near the formula value (~553 A from
                # I_fault at r_line=0.10/x_line=0.30/r_fault=11.0, rounded to the
                # 550 A load in the queries). t_op/t_clear are scenario values:
                # the IEC function would return its 10000.0 ms below-pickup
                # sentinel here, which is precisely the misoperation under test.
                i_fault = 550.0
                t_op = 22.0
                t_clear = 55.0
            else:
                # Fully formula-derived modes (GENUINE_PHASE_C_OVERCURRENT,
                # CT_PHASE_INVERSION): modulate resistance per case.
                if len(dev_cases) < total_target_dev:
                    perturb = 1.0 + ((i % 5) - 2) * 0.03
                else:
                    # Held-out resample: half-step-offset perturbation grid that
                    # interleaves with (never equals) the dev grid, so every
                    # formula-derived fault current is disjoint from dev values.
                    perturb = 1.0 + (((i + 2) % 5) - 2) * 0.03 + 0.015
                r_l = var["r_line"] * perturb
                x_l = var["x_line"] * perturb
                r_f = var["r_fault"]
                i_fault = cls.calculate_fault_current(r_l, x_l, r_f)
                t_op = cls.calculate_iec_trip_time_ms(i_fault)
                t_clear = round(t_op + 35.0, 1)

            # Audit expected_fact_keywords per mode to match what the pipeline genuinely emits:
            # - Documentation QA cases emit ANSI protection literature from DOC-PROT-001
            # - Abstention cases emit "insufficient" from the sufficiency evaluation
            # - Misoperation cases emit "Misoperation" from the diagnosis title and the feeder ID
            # - Standard fault and topology cases emit the feeder identifier (e.g. "F12" / "F13")
            if var["mode"] == "DOCUMENTATION_QA":
                expected_facts = ["DOC-PROT-001"]
            elif var["mode"] in ["TRUNCATED_RECORDING_ABSTENTION", "UNRESOLVABLE_TELEMETRY_CONTRADICTION"]:
                expected_facts = [var["feeder"], "insufficient"]
            elif var["mode"] == "SETTINGS_MISOPERATION":
                expected_facts = [var["feeder"], "Misoperation"]
            else:
                expected_facts = [var["feeder"]]

            case = LatentTestCase(
                case_id=f"TC-LATENT-{case_idx:03d}",
                failure_mode=var["mode"],
                query=f"{query} [Run #{case_idx}]",
                target_incident_id=var["incident_id"],
                target_feeder_id=var["feeder"],
                expected_investigation_type=var["type"],
                expected_top_hypothesis_code=var["hyp"],
                expected_sufficiency=var["suff"],
                expected_tool_calls=var["tools"],
                expected_fact_keywords=expected_facts,
                ground_truth_fault_current_a=i_fault,
                ground_truth_fault_phase=var["phase"],
                ground_truth_operating_time_ms=t_op,
                ground_truth_clearing_time_ms=t_clear,
                is_negative_case=(not var["suff"]),
                notes=f"Analytical physics-derived test case for {var['mode']}.",
            )

            if len(dev_cases) < total_target_dev:
                dev_cases.append(case)
            else:
                heldout_cases.append(case)
            case_idx += 1

        return dev_cases, heldout_cases

    @classmethod
    def save_cases_to_disk(cls):
        os.makedirs(EVAL_DIR, exist_ok=True)
        dev, heldout = cls.generate_all_cases()

        dev_path = EVAL_DIR / "dev_cases.json"
        heldout_path = EVAL_DIR / "heldout_cases.json"

        with open(dev_path, "w", encoding="utf-8") as f:
            json.dump([c.model_dump() for c in dev], f, indent=2)

        with open(heldout_path, "w", encoding="utf-8") as f:
            json.dump([c.model_dump() for c in heldout], f, indent=2)

        print(f"Saved {len(dev)} dev cases to {dev_path}")
        print(f"Saved {len(heldout)} held-out cases to {heldout_path}")
        return dev, heldout


if __name__ == "__main__":
    GroundTruthGenerator.save_cases_to_disk()
