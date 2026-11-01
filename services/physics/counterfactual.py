"""Counterfactual fault-current and operating-time calculations.

Equations:
  I = V_LN / sqrt((Rs+R_line+Rf)^2 + (Xs+X_line)^2)
  t_op = 0.14*TD / ((I/Ipickup)^0.02 - 1)   [IEC 60255 normal-inverse overcurrent]
  t_clear = t_op + t_mech (35ms breaker)

The timing helper is deliberately limited to the IEC 60255 normal-inverse
curve; it is not a general relay-curve or definite-time model.
"""
from __future__ import annotations

import math
from pydantic import BaseModel, Field


V_LN = 6350.85
R_SOURCE = 0.25
X_SOURCE = 1.45
T_MECH_MS = 35.0


class CounterfactualInput(BaseModel):
    r_line: float = Field(ge=0, le=5)
    x_line: float = Field(ge=0, le=5)
    r_fault: float = Field(ge=0, le=100)
    pickup_a: float = 2500.0
    time_dial: float = 0.1


class CounterfactualResult(BaseModel):
    fault_current_a: float
    operating_time_ms: float
    clearing_time_ms: float
    would_trip: bool
    narrative_numbers: str  # exact string the LLM must reuse


def iec_trip_time_ms(current_a: float, pickup_a: float, time_dial: float) -> float:
    if current_a <= pickup_a:
        return 10000.0
    m = current_a / pickup_a
    return round((0.14 * time_dial) / (math.pow(m, 0.02) - 1.0) * 1000.0, 2)


def fault_current_a(r_line: float, x_line: float, r_fault: float) -> float:
    r = R_SOURCE + r_line + r_fault
    x = X_SOURCE + x_line
    return round(V_LN / math.sqrt(r * r + x * x), 2)


def simulate(inp: CounterfactualInput) -> CounterfactualResult:
    i_f = fault_current_a(inp.r_line, inp.x_line, inp.r_fault)
    t_op = iec_trip_time_ms(i_f, inp.pickup_a, inp.time_dial)
    would_trip = i_f > inp.pickup_a
    t_clear = round(t_op + T_MECH_MS, 2) if would_trip else 10000.0
    nums = (
        f"fault current {i_f} A, operating time {t_op} ms, "
        f"clearing time {t_clear} ms, would_trip={would_trip}"
    )
    return CounterfactualResult(
        fault_current_a=i_f,
        operating_time_ms=t_op,
        clearing_time_ms=t_clear,
        would_trip=would_trip,
        narrative_numbers=nums,
    )


def describe_scenario_change(base_r_fault: float, new_r_fault: float) -> str:
    ratio = (new_r_fault / base_r_fault) if base_r_fault > 0 else float("inf")
    return f"fault resistance {base_r_fault} -> {new_r_fault} ohm (x{ratio:.2f})"
