"""Deterministic SI unit canonicalization and dimensional checking for power system quantities."""
from enum import Enum
from typing import Optional, Tuple, Dict
import re


class PhysicalDimension(str, Enum):
    CURRENT = "CURRENT"
    VOLTAGE = "VOLTAGE"
    TIME = "TIME"
    FREQUENCY = "FREQUENCY"
    PERCENT = "PERCENT"
    DIMENSIONLESS = "DIMENSIONLESS"


# Registry mapping normalized unit text -> (PhysicalDimension, multiplier_to_base_unit, canonical_symbol)
# Base units: Current = A, Voltage = V, Time = s, Frequency = Hz, Percent = %
UNIT_REGISTRY: Dict[str, Tuple[PhysicalDimension, float, str]] = {
    # Current
    "A": (PhysicalDimension.CURRENT, 1.0, "A"),
    "AMP": (PhysicalDimension.CURRENT, 1.0, "A"),
    "AMPS": (PhysicalDimension.CURRENT, 1.0, "A"),
    "AMPERE": (PhysicalDimension.CURRENT, 1.0, "A"),
    "AMPERES": (PhysicalDimension.CURRENT, 1.0, "A"),
    "KA": (PhysicalDimension.CURRENT, 1000.0, "A"),
    "KILOAMP": (PhysicalDimension.CURRENT, 1000.0, "A"),
    "KILOAMPS": (PhysicalDimension.CURRENT, 1000.0, "A"),
    "MEGAAMP": (PhysicalDimension.CURRENT, 1000000.0, "A"),
    "MEGAAMPS": (PhysicalDimension.CURRENT, 1000000.0, "A"),
    # Milliamp: SI-correct lowercase "mA" resolves exact-case below; bare
    # uppercase "MA" is megaamp (see parse_unit). Spelled-out forms unambiguous.
    "mA": (PhysicalDimension.CURRENT, 0.001, "A"),
    "MILLIAMP": (PhysicalDimension.CURRENT, 0.001, "A"),
    "MILLIAMPS": (PhysicalDimension.CURRENT, 0.001, "A"),

    # Voltage
    "V": (PhysicalDimension.VOLTAGE, 1.0, "V"),
    "VOLT": (PhysicalDimension.VOLTAGE, 1.0, "V"),
    "VOLTS": (PhysicalDimension.VOLTAGE, 1.0, "V"),
    "KV": (PhysicalDimension.VOLTAGE, 1000.0, "V"),
    "KILOVOLT": (PhysicalDimension.VOLTAGE, 1000.0, "V"),
    "KILOVOLTS": (PhysicalDimension.VOLTAGE, 1000.0, "V"),
    # Megavolt: SI-correct uppercase "MV" resolves exact-case below; lowercase
    # "mV" is millivolt (see parse_unit). Spelled-out forms unambiguous.
    "MV": (PhysicalDimension.VOLTAGE, 1000000.0, "V"),
    "MEGAVOLT": (PhysicalDimension.VOLTAGE, 1000000.0, "V"),
    "MEGAVOLTS": (PhysicalDimension.VOLTAGE, 1000000.0, "V"),
    "mV": (PhysicalDimension.VOLTAGE, 0.001, "V"),
    "MILLIVOLT": (PhysicalDimension.VOLTAGE, 0.001, "V"),
    "MILLIVOLTS": (PhysicalDimension.VOLTAGE, 0.001, "V"),

    # Time
    "S": (PhysicalDimension.TIME, 1.0, "s"),
    "SEC": (PhysicalDimension.TIME, 1.0, "s"),
    "SECS": (PhysicalDimension.TIME, 1.0, "s"),
    "SECOND": (PhysicalDimension.TIME, 1.0, "s"),
    "SECONDS": (PhysicalDimension.TIME, 1.0, "s"),
    "MS": (PhysicalDimension.TIME, 0.001, "s"),
    "MSEC": (PhysicalDimension.TIME, 0.001, "s"),
    "MSECS": (PhysicalDimension.TIME, 0.001, "s"),
    "MILLISECOND": (PhysicalDimension.TIME, 0.001, "s"),
    "MILLISECONDS": (PhysicalDimension.TIME, 0.001, "s"),

    # Frequency
    "HZ": (PhysicalDimension.FREQUENCY, 1.0, "Hz"),
    "HERTZ": (PhysicalDimension.FREQUENCY, 1.0, "Hz"),
    "KHZ": (PhysicalDimension.FREQUENCY, 1000.0, "Hz"),

    # Percent
    "%": (PhysicalDimension.PERCENT, 1.0, "%"),
    "PERCENT": (PhysicalDimension.PERCENT, 1.0, "%"),
    "PCT": (PhysicalDimension.PERCENT, 1.0, "%"),
}


def normalize_unit_string(unit: Optional[str]) -> str:
    """Normalizes raw unit string by stripping punctuation and whitespace.

    Case is preserved: SI prefixes are case-sensitive ("mA" milliamp vs "MA"
    megaamp, "mV" millivolt vs "MV" megavolt). parse_unit falls back to an
    uppercased lookup for case-insensitive symbols (A, V, MS, ...).
    """
    if not unit:
        return ""
    return re.sub(r"[^\w%]", "", unit.strip())


def parse_unit(unit: Optional[str]) -> Optional[Tuple[PhysicalDimension, float, str]]:
    """
    Parses a unit string into its physical dimension, multiplier to base unit, and canonical symbol.
    Returns None if the unit is unknown or unassigned.
    """
    norm = normalize_unit_string(unit)
    if not norm:
        return None
    if norm in UNIT_REGISTRY:
        return UNIT_REGISTRY[norm]
    return UNIT_REGISTRY.get(norm.upper())


def canonicalize_quantity(value: float, unit: Optional[str]) -> Tuple[float, Optional[str], Optional[PhysicalDimension]]:
    """
    Converts a value and unit into its canonical base representation.
    Returns (canonical_value, base_unit_symbol, dimension).
    Example: (3.75863, "kA") -> (3758.63, "A", PhysicalDimension.CURRENT).
    """
    parsed = parse_unit(unit)
    if parsed is None:
        return value, unit, None
    dim, multiplier, base_symbol = parsed
    return round(value * multiplier, 6), base_symbol, dim


def are_quantities_compatible(
    val_a: float,
    unit_a: Optional[str],
    val_b: float,
    unit_b: Optional[str],
    tolerance_pct: float = 0.5,
) -> Tuple[bool, str]:
    """
    Compares two numerical quantities with unit awareness, prefix scaling, and dimensional safety.

    Rules:
    1. If both have units:
       - Must have matching physical dimensions (e.g. Current vs Voltage rejected).
       - Scaled to canonical base unit and compared within tolerance_pct.
    2. If only one has a unit:
       - If unitless value matches either the raw value or canonical value within tolerance,
         and no dimensional conflict exists, allow match.
    3. If neither has a unit:
       - Compare raw values within tolerance_pct.

    Returns:
        (is_match: bool, reason: str)
    """
    canon_a, base_a, dim_a = canonicalize_quantity(val_a, unit_a)
    canon_b, base_b, dim_b = canonicalize_quantity(val_b, unit_b)

    # 1. Both have recognized dimensions: dimension must match!
    if dim_a is not None and dim_b is not None:
        if dim_a != dim_b:
            return False, f"Incompatible physical dimensions: '{dim_a.value}' ({unit_a}) vs '{dim_b.value}' ({unit_b})"

        diff = abs(canon_a - canon_b)
        threshold = max((tolerance_pct / 100.0) * abs(canon_b), 1e-4)
        if diff <= threshold:
            return True, f"Matched within ±{tolerance_pct}% ({canon_a} {base_a} ~ {canon_b} {base_b})"
        rel_err = (diff / max(abs(canon_b), 1e-6)) * 100.0
        return False, f"Value mismatch: {val_a} {unit_a} ({canon_a} {base_a}) vs {val_b} {unit_b} ({canon_b} {base_b}) [rel error {rel_err:.2f}% > {tolerance_pct}%]"

    # 2. One has recognized dimension, other is unitless
    if (dim_a is not None and dim_b is None) or (dim_a is None and dim_b is not None):
        # Compare canonical vs raw
        target_val = canon_a if dim_a is not None else canon_b
        raw_val = val_b if dim_a is not None else val_a
        diff = abs(target_val - raw_val)
        threshold = max((tolerance_pct / 100.0) * abs(target_val), 1e-4)
        if diff <= threshold:
            return True, f"Matched unitless with canonical: {raw_val} ~ {target_val}"

        # Also check direct raw match in case the unitless value was stated in the prefixed unit
        raw_diff = abs(val_a - val_b)
        raw_threshold = max((tolerance_pct / 100.0) * abs(val_b), 1e-4)
        if raw_diff <= raw_threshold:
            return True, f"Matched unitless with raw: {val_a} ~ {val_b}"

        return False, f"Value mismatch between {val_a} ({unit_a or 'unitless'}) and {val_b} ({unit_b or 'unitless'})"

    # 3. Neither has recognized dimension (pure numbers)
    diff = abs(val_a - val_b)
    threshold = max((tolerance_pct / 100.0) * abs(val_b), 1e-4)
    if diff <= threshold:
        return True, f"Matched unitless: {val_a} ~ {val_b}"
    rel_err = (diff / max(abs(val_b), 1e-6)) * 100.0
    return False, f"Unitless mismatch: {val_a} vs {val_b} [rel error {rel_err:.2f}% > {tolerance_pct}%]"
