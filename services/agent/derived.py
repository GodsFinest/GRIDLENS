"""Secondary-current arithmetic with an explicit cited CT ratio and full grammar."""
import math
import re
from domain.evidence.models import EvidenceKind
from services.agent.units import are_quantities_compatible


class DerivedQuantityCrossChecker:
    @classmethod
    def check_derived_claim(cls, claim, evidence_dict, tolerance_pct=0.5):
        match = re.fullmatch(r"Channel ([A-Za-z0-9_]+) secondary RMS current = ([0-9]+(?:\.[0-9]+)?) (A|kA)\.", claim.statement)
        if not match:
            return None
        if len(claim.evidence_ids) != 1:
            return False, "One cited channel with CT-ratio metadata is required."
        ev = evidence_dict.get(claim.evidence_ids[0])
        if ev is None or ev.kind != EvidenceKind.CHANNEL_RMS or ev.unit != "A":
            return False, "A cited primary-current measurement is required."
        ratio = ev.metadata.get("ct_ratio")
        if (ev.metadata.get("channel") != match[1] or type(ratio) not in (int, float) or
                not math.isfinite(ratio) or ratio <= 0 or type(ev.structured_value) not in (int, float)):
            return False, "Explicit channel binding and finite positive CT ratio are required."
        expected = ev.structured_value / ratio
        valid, reason = are_quantities_compatible(float(match[2]), match[3], expected, "A", tolerance_pct=tolerance_pct)
        return valid, reason
