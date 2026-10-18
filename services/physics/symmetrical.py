"""Deterministic symmetrical-components fault classifier.

Substation theory (Fortescue): unbalanced phase currents decompose into
zero / positive / negative sequence components:
  I0 = (Ia + Ib + Ic) / 3
  I1 = (Ia + a*Ib + a^2*Ic) / 3
  I2 = (Ia + a^2*Ib + a*Ic) / 3   where a = e^(j120deg)

Two input paths, deliberately separated:

* PHASOR path (authoritative): caller supplies magnitudes AND angles.
  Sequence values and the fault-type decision both come from the true
  complex phasors. A B-C phase-to-phase fault has its two faulted
  phases ~180 deg apart, giving near-zero I0 (LL); ground involvement
  shows up as significant I0 (LLG). This distinction is invisible to
  magnitudes alone.

* RMS path (magnitude-only triage): caller supplies RMS magnitudes only.
  Sequence components CANNOT be computed from magnitudes — assuming a
  nominal 120 deg separation fabricates I0 (e.g. a true LL fault reports
  a phantom ~1 kA zero-sequence). So this path reports NO sequence
  numbers (sequence_trusted=False, magnitudes zeroed) and never claims
  LL vs LLG; two faulted phases yield an explicit ambiguous label that
  directs the caller to the phasor path. Balanced-over-pickup yields 3-PH
  (a balanced high-current fault is a fault, not "no fault").

The LLM may *explain* results in words, but classification numbers always
come from this module, so every figure in a report is verifiable.
"""
from __future__ import annotations

import cmath
import math
from typing import Dict, Tuple
from pydantic import BaseModel, Field


A = cmath.exp(complex(0, 2 * math.pi / 3))
A2 = A * A

DEFAULT_PICKUP_A = 2500.0
# Zero-sequence significance threshold: I0/I1 above this means ground is involved.
GROUND_INVOLVEMENT_RATIO = 0.15
# Magnitude balance tolerance for "all three phases agree".
BALANCE_TOLERANCE = 0.15


class SequenceComponents(BaseModel):
    i0_mag: float
    i1_mag: float
    i2_mag: float
    i0_angle_deg: float
    i1_angle_deg: float
    i2_angle_deg: float


class FaultClassification(BaseModel):
    fault_type: str  # e.g. "C-G (LG)", "B-C (LL)", "B-C-G (LLG)", "3-PH", "BALANCED"
    faulted_phase: str  # "A" | "B" | "C" | "BC" | ... | "ABC" | "NONE"
    i0_mag: float
    i1_mag: float
    i2_mag: float
    unbalance_ratio: float  # (I0+I2)/I1, ~0 for balanced
    explanation: str
    basis: str = "PHASOR"  # "PHASOR" (trusted) | "RMS_MAGNITUDE_ONLY" (triage)
    sequence_trusted: bool = True  # False when i0/i1/i2 are placeholders


def phasor(mag: float, angle_deg: float) -> complex:
    return cmath.rect(mag, math.radians(angle_deg))


def decompose(ia: complex, ib: complex, ic: complex) -> SequenceComponents:
    i0 = (ia + ib + ic) / 3.0
    i1 = (ia + A * ib + A2 * ic) / 3.0
    i2 = (ia + A2 * ib + A * ic) / 3.0
    return SequenceComponents(
        i0_mag=round(abs(i0), 2),
        i1_mag=round(abs(i1), 2),
        i2_mag=round(abs(i2), 2),
        i0_angle_deg=round(math.degrees(cmath.phase(i0)), 2),
        i1_angle_deg=round(math.degrees(cmath.phase(i1)), 2),
        i2_angle_deg=round(math.degrees(cmath.phase(i2)), 2),
    )


def _magnitudes_balanced(mags: Dict[str, float]) -> bool:
    mean = sum(mags.values()) / 3.0
    if mean <= 0:
        return True
    return all(abs(v - mean) / mean < BALANCE_TOLERANCE for v in mags.values())


def classify_from_phasors(
    ia: complex,
    ib: complex,
    ic: complex,
    pickup_a: float = DEFAULT_PICKUP_A,
) -> FaultClassification:
    """Authoritative classification from true complex phase-current phasors."""
    seq = decompose(ia, ib, ic)
    mags: Dict[str, float] = {"A": abs(ia), "B": abs(ib), "C": abs(ic)}
    denom = max(seq.i1_mag, 1e-6)
    unbalance = round((seq.i0_mag + seq.i2_mag) / denom, 3)
    ground_involved = seq.i0_mag > GROUND_INVOLVEMENT_RATIO * seq.i1_mag

    if _magnitudes_balanced(mags):
        mean = sum(mags.values()) / 3.0
        if mean >= pickup_a:
            return FaultClassification(
                fault_type="3-PH",
                faulted_phase="ABC",
                i0_mag=seq.i0_mag, i1_mag=seq.i1_mag, i2_mag=seq.i2_mag,
                unbalance_ratio=unbalance,
                explanation=(
                    f"Balanced overcurrent ({round(mean, 1)} A >= pickup {pickup_a} A) on all "
                    f"three phases with negligible unbalance ({unbalance}): three-phase fault. "
                    f"I0={seq.i0_mag}A I1={seq.i1_mag}A I2={seq.i2_mag}A."
                ),
            )
        return FaultClassification(
            fault_type="BALANCED",
            faulted_phase="NONE",
            i0_mag=seq.i0_mag, i1_mag=seq.i1_mag, i2_mag=seq.i2_mag,
            unbalance_ratio=unbalance,
            explanation=(
                f"Balanced load below pickup ({round(mean, 1)} A < {pickup_a} A); "
                f"negligible zero/negative sequence."
            ),
        )

    ranked = sorted(mags.items(), key=lambda kv: kv[1], reverse=True)
    (top_phase, top_mag) = ranked[0]
    (second_phase, second_mag) = ranked[1]
    third_mag = ranked[2][1]

    if top_mag > 2.0 * second_mag:
        return FaultClassification(
            fault_type=f"{top_phase}-G (LG)",
            faulted_phase=top_phase,
            i0_mag=seq.i0_mag, i1_mag=seq.i1_mag, i2_mag=seq.i2_mag,
            unbalance_ratio=unbalance,
            explanation=(
                f"Single dominant phase {top_phase} ({round(top_mag, 1)} A vs "
                f"{round(second_mag, 1)} A next): line-to-ground fault. "
                f"I0={seq.i0_mag}A I1={seq.i1_mag}A I2={seq.i2_mag}A."
            ),
        )

    if top_mag > 1.5 * third_mag and second_mag > 1.5 * third_mag:
        pair = "".join(sorted([top_phase, second_phase]))
        if ground_involved:
            return FaultClassification(
                fault_type=f"{top_phase}-{second_phase}-G (LLG)",
                faulted_phase=pair,
                i0_mag=seq.i0_mag, i1_mag=seq.i1_mag, i2_mag=seq.i2_mag,
                unbalance_ratio=unbalance,
                explanation=(
                    f"Two faulted phases {top_phase}/{second_phase} with significant zero "
                    f"sequence (I0={seq.i0_mag}A > {GROUND_INVOLVEMENT_RATIO}xI1): "
                    f"line-to-line-to-ground fault."
                ),
            )
        return FaultClassification(
            fault_type=f"{top_phase}-{second_phase} (LL)",
            faulted_phase=pair,
            i0_mag=seq.i0_mag, i1_mag=seq.i1_mag, i2_mag=seq.i2_mag,
            unbalance_ratio=unbalance,
            explanation=(
                f"Two faulted phases {top_phase}/{second_phase} with negligible zero "
                f"sequence (I0={seq.i0_mag}A): phase-to-phase fault, no ground involvement."
            ),
        )

    if max(mags.values()) >= pickup_a:
        return FaultClassification(
            fault_type="3-PH",
            faulted_phase="ABC",
            i0_mag=seq.i0_mag, i1_mag=seq.i1_mag, i2_mag=seq.i2_mag,
            unbalance_ratio=unbalance,
            explanation=(
                f"Unbalanced overcurrent across all three phases {mags}: evolving or "
                f"three-phase fault. I0={seq.i0_mag}A I1={seq.i1_mag}A I2={seq.i2_mag}A."
            ),
        )
    return FaultClassification(
        fault_type="UNBALANCED LOAD",
        faulted_phase="NONE",
        i0_mag=seq.i0_mag, i1_mag=seq.i1_mag, i2_mag=seq.i2_mag,
        unbalance_ratio=unbalance,
        explanation=f"Unbalanced magnitudes {mags} below pickup {pickup_a} A: load unbalance, not a fault.",
    )


def classify_from_measurements(
    measurements: Dict[str, Tuple[float, float]],
    pickup_a: float = DEFAULT_PICKUP_A,
) -> FaultClassification:
    """Full-phasor path: {phase: (rms, angle_deg)} for A/B/C.

    The type decision uses the true complex phasors — never the
    magnitude-only heuristic.
    """
    ia = phasor(*measurements["A"])
    ib = phasor(*measurements["B"])
    ic = phasor(*measurements["C"])
    return classify_from_phasors(ia, ib, ic, pickup_a=pickup_a)


def classify_from_rms(
    ia_rms: float,
    ib_rms: float,
    ic_rms: float,
    pickup_a: float = DEFAULT_PICKUP_A,
) -> FaultClassification:
    """Magnitude-only triage. Reports NO sequence numbers.

    Sequence components require phase angles; any I0/I2 derived from
    magnitudes alone (e.g. by assuming 120 deg separation) is fabricated
    for real faults, whose faulted phases are not 120 deg apart. Callers
    needing LL-vs-LLG resolution must use the phasor path.
    """
    mags: Dict[str, float] = {"A": ia_rms, "B": ib_rms, "C": ic_rms}
    mean = sum(mags.values()) / 3.0

    def _unttrusted(fault_type: str, faulted: str, explanation: str) -> FaultClassification:
        return FaultClassification(
            fault_type=fault_type,
            faulted_phase=faulted,
            i0_mag=0.0, i1_mag=0.0, i2_mag=0.0,
            unbalance_ratio=0.0,
            explanation=explanation + " (RMS magnitudes only; sequence values require phasor angles.)",
            basis="RMS_MAGNITUDE_ONLY",
            sequence_trusted=False,
        )

    if _magnitudes_balanced(mags):
        if mean >= pickup_a:
            return _unttrusted(
                "3-PH (RMS triage)",
                "ABC",
                f"Balanced overcurrent ({round(mean, 1)} A >= pickup {pickup_a} A): probable three-phase fault; confirm with phasors.",
            )
        return _unttrusted(
            "BALANCED",
            "NONE",
            f"Balanced magnitudes below pickup ({round(mean, 1)} A < {pickup_a} A).",
        )

    ranked = sorted(mags.items(), key=lambda kv: kv[1], reverse=True)
    (top_phase, top_mag) = ranked[0]
    (second_phase, second_mag) = ranked[1]
    third_mag = ranked[2][1]

    if top_mag > 2.0 * second_mag:
        return _unttrusted(
            f"{top_phase}-G (LG, RMS triage)",
            top_phase,
            f"Single dominant phase {top_phase} ({round(top_mag, 1)} A): probable line-to-ground fault; confirm I0 with phasors.",
        )

    if top_mag > 1.5 * third_mag and second_mag > 1.5 * third_mag:
        pair = "".join(sorted([top_phase, second_phase]))
        return _unttrusted(
            f"{top_phase}-{second_phase} (LL or LLG — phasor angles required)",
            pair,
            f"Two elevated phases {top_phase}/{second_phase}: LL vs LLG cannot be resolved from magnitudes (I0 needs angles).",
        )

    if max(mags.values()) >= pickup_a:
        return _unttrusted(
            "3-PH (RMS triage)",
            "ABC",
            f"Overcurrent across phases {mags}: probable three-phase fault; confirm with phasors.",
        )
    return _unttrusted(
        "UNBALANCED LOAD",
        "NONE",
        f"Unbalanced magnitudes {mags} below pickup {pickup_a} A.",
    )
