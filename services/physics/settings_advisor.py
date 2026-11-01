"""Relay-setting constraint checks.

Substation theory: an overcurrent pickup must satisfy
  max_load * 1.25  <  pickup  <  min_fault / 1.5   (sensitivity >= 1.5)
and time-dial must keep IEC operating time within breaker capability.

Only this module assigns the final valid or invalid verdict.
"""
from __future__ import annotations

from typing import List
from pydantic import BaseModel, Field

from services.physics.counterfactual import iec_trip_time_ms


class SettingProposal(BaseModel):
    pickup_a: float = Field(gt=0, le=10000)
    time_dial: float = Field(gt=0, le=2.0)


class SettingVerdict(BaseModel):
    valid: bool
    pickup_a: float
    time_dial: float
    sensitivity: float  # min_fault / pickup, must be >= 1.5
    load_margin: float  # pickup / max_load, must be >= 1.25
    operating_time_ms: float
    violations: List[str]


def evaluate(
    proposal: SettingProposal,
    max_load_a: float,
    min_fault_a: float,
    max_breaker_time_ms: float = 2000.0,
) -> SettingVerdict:
    violations: List[str] = []
    sensitivity = round(min_fault_a / proposal.pickup_a, 3) if proposal.pickup_a > 0 else 0.0
    load_margin = round(proposal.pickup_a / max_load_a, 3) if max_load_a > 0 else 0.0
    t_op = iec_trip_time_ms(min_fault_a, proposal.pickup_a, proposal.time_dial)

    if load_margin < 1.25:
        violations.append(
            f"Pickup {proposal.pickup_a}A too low: margin {load_margin} < 1.25 over max load {max_load_a}A (spurious trip risk, cf INC-2026-005)."
        )
    if sensitivity < 1.5:
        violations.append(
            f"Pickup {proposal.pickup_a}A too high: sensitivity {sensitivity} < 1.5 for min fault {min_fault_a}A (missed-trip risk)."
        )
    if t_op > max_breaker_time_ms:
        violations.append(f"Operating time {t_op}ms exceeds breaker capability {max_breaker_time_ms}ms; lower time-dial.")
    return SettingVerdict(
        valid=len(violations) == 0,
        pickup_a=proposal.pickup_a,
        time_dial=proposal.time_dial,
        sensitivity=sensitivity,
        load_margin=load_margin,
        operating_time_ms=t_op,
        violations=violations,
    )
