"""Executable, narrow inference rules; the ledger is trusted tool output.

Each conclusion is regenerated from typed cited evidence. These rules establish
observations, not a relay's internal causal mechanism or general NL entailment.
"""
import math
from domain.evidence.models import EvidenceKind as K

OVERCURRENT = "INF_RULE_MEASURED_OVERCURRENT"
INCOMPLETE = "INF_RULE_INSUFFICIENT_RECORD"
RULE_IDS = (OVERCURRENT, INCOMPLETE)


def derive(rule_id, evidence):
    items = list(evidence)
    if not items or any(not e.deterministic for e in items):
        return None
    if rule_id == OVERCURRENT:
        flags = [e for e in items if e.kind == K.OVERCURRENT_EXCEEDED]
        currents = [e for e in items if e.kind == K.CHANNEL_RMS]
        if len(flags) != 1 or len(currents) != 1 or len(items) != 2:
            return None
        flag, current = flags[0], currents[0]
        phase = str(current.metadata.get("phase", "")).upper().removeprefix("I")
        flag_phase = str(flag.metadata.get("fault_phase", "")).upper().removeprefix("I")
        threshold, value = flag.metadata.get("pickup_threshold_a"), current.structured_value
        if (phase not in {"A", "B", "C"} or flag_phase != phase or
                flag.structured_value is not True or current.unit != "A" or
                type(value) not in (int, float) or type(threshold) not in (int, float) or
                not math.isfinite(value) or not math.isfinite(threshold) or
                threshold <= 0 or value < threshold or current.source_id != flag.source_id):
            return None
        return {"phase": phase, "fault_rms_a": float(value), "pickup_a": float(threshold)}
    if rule_id == INCOMPLETE:
        if len(items) == 1 and items[0].kind == K.RECORDING_TRUNCATED and items[0].structured_value is True:
            return {"record_complete": False}
    return None


def render(rule_id, result):
    if rule_id == OVERCURRENT:
        return (f"Measured Phase {result['phase']} fault-window RMS current "
                f"({result['fault_rms_a']:.2f} A) met or exceeded the configured "
                f"pickup threshold ({result['pickup_a']:.2f} A). "
                "This observation alone does not establish the cause of the relay trip.")
    if rule_id == INCOMPLETE:
        return "The waveform evidence is incomplete or unavailable; it cannot establish the full event sequence or whether the disturbance was cleared."
    raise ValueError("Unsupported inference rule")


RECOMMENDATIONS = (
    "Have a qualified protection engineer review the cited measurements, relay settings, and event sequence before deciding on field action.",
    "Retrieve the complete recording and verify channel metadata before drawing a final conclusion.",
    "Verify the channel-to-phase mapping against the approved wiring documentation and independent measurements.",
)
