"""PhysicsTool: agent-invokable deterministic protection-analysis tools.

This is the GenAI integration point the standalone calculators lacked:
the investigation graph calls this tool (not raw functions), its typed
results land in ``raw_tool_results["PhysicsTool"]``, and the evidence
factory converts them into ledger facts any LLM narrative must cite.
Counterfactual what-ifs remain user-driven via the /physics API; the
symmetrical classification + setting check run in-pipeline on measured
waveform data for every protection-event investigation.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from pydantic import BaseModel, Field

from services.physics.symmetrical import (
    FaultClassification,
    classify_from_measurements,
    classify_from_rms,
)
from services.physics.settings_advisor import SettingProposal, SettingVerdict, evaluate


class PhysicsAnalysisResult(BaseModel):
    incident_id: str
    feeder_id: str
    classification: Optional[FaultClassification] = None
    classification_basis: str = "NONE"  # "PHASOR" | "RMS_MAGNITUDE_ONLY" | "SKIPPED"
    skip_reason: Optional[str] = None
    setting_verdict: Optional[SettingVerdict] = None
    setting_check_skipped_reason: Optional[str] = None
    metadata: Dict[str, object] = Field(default_factory=dict)


class PhysicsTool:
    """Deterministic protection-analysis tool for agent orchestration."""

    async def execute_symmetrical(
        self,
        incident_id: str,
        feeder_id: str,
        phase_rms: Dict[str, float],
        pickup_a: float = 2500.0,
        phasor_angles: Optional[Dict[str, float]] = None,
        max_load_a: Optional[float] = None,
        time_dial: float = 0.1,
    ) -> PhysicsAnalysisResult:
        """Classify fault type from measured phase currents; check pickup setting.

        ``phase_rms`` maps phase letter -> fault RMS amps. When COMTRADE
        phasor angles are supplied they are used (authoritative path);
        otherwise magnitude-only triage runs and reports sequence_trusted=False.
        The setting check compares the active pickup against measured fault
        current and feeder continuous rating; it is skipped when inputs are
        missing rather than guessed.
        """
        if phasor_angles:
            measurements: Dict[str, Tuple[float, float]] = {
                ph: (phase_rms[ph], phasor_angles[ph]) for ph in ("A", "B", "C") if ph in phase_rms
            }
            if len(measurements) < 3:
                return PhysicsAnalysisResult(
                    incident_id=incident_id, feeder_id=feeder_id,
                    classification_basis="SKIPPED",
                    skip_reason="Phasor angles incomplete; need A/B/C.",
                    setting_check_skipped_reason="Classification skipped.",
                )
            classification = classify_from_measurements(measurements, pickup_a=pickup_a)
            basis = "PHASOR"
        else:
            if not all(ph in phase_rms for ph in ("A", "B", "C")):
                return PhysicsAnalysisResult(
                    incident_id=incident_id, feeder_id=feeder_id,
                    classification_basis="SKIPPED",
                    skip_reason="Fewer than three current phases measured.",
                    setting_check_skipped_reason="Classification skipped.",
                )
            classification = classify_from_rms(
                phase_rms["A"], phase_rms["B"], phase_rms["C"], pickup_a=pickup_a
            )
            basis = "RMS_MAGNITUDE_ONLY"

        verdict: Optional[SettingVerdict] = None
        setting_skip: Optional[str] = None
        fault_peak = max(phase_rms.get(ph, 0.0) for ph in ("A", "B", "C"))
        if max_load_a is None:
            setting_skip = "Feeder continuous rating unavailable; setting check skipped."
        elif fault_peak <= 0:
            setting_skip = "No measured fault current; setting check skipped."
        elif fault_peak <= pickup_a:
            # Below pickup there is no fault for the setting to be sensitive
            # to; spurious trips here are the H2 settings-misoperation path
            # (cf INC-2026-005), not a sensitivity failure.
            setting_skip = (
                f"Measured peak {round(fault_peak, 1)} A below pickup {pickup_a} A; "
                "sensitivity check not applicable."
            )
        else:
            verdict = evaluate(
                SettingProposal(pickup_a=pickup_a, time_dial=time_dial),
                max_load_a=max_load_a,
                min_fault_a=fault_peak,
            )

        return PhysicsAnalysisResult(
            incident_id=incident_id,
            feeder_id=feeder_id,
            classification=classification,
            classification_basis=basis,
            setting_verdict=verdict,
            setting_check_skipped_reason=setting_skip,
            metadata={"pickup_a": pickup_a, "time_dial": time_dial, "max_load_a": max_load_a},
        )
