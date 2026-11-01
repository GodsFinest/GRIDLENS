"""Validate generated report text against the verified evidence ledger."""
import re
from typing import List, Tuple, Set


class FaithfulnessVerifier:
    """Check report entities and measurements against verified claims."""

    ENTITY_PATTERNS = [
        re.compile(r"\b(F\d+)\b", re.IGNORECASE),                         # Feeders: F12, F13
        re.compile(r"\b(CB\d+)\b", re.IGNORECASE),                        # Breakers: CB12, CB13
        re.compile(r"\b(RELAY[_-]\d+)\b", re.IGNORECASE),                 # Relays: RELAY_12
        re.compile(r"\b(IED[_-]\d+)\b", re.IGNORECASE),                   # IEDs: IED_12
        re.compile(r"\b(BAY_[A-Z0-9]+)\b", re.IGNORECASE),                # Bays: BAY_F12
        re.compile(r"\b(OGS[_-]\d+)\b", re.IGNORECASE),                   # Substations: OGS-01
        re.compile(r"\b(BUS_[A-Z0-9]+)\b", re.IGNORECASE),                # Buses: BUS_B
        re.compile(r"\b(CT\d+[A-Z]?|VT\d+)\b", re.IGNORECASE),            # Sensors: CT12A, VT12
    ]

    # Pattern for quantitative numbers with optional units
    QUANTITY_PATTERN = re.compile(
        r"(?<![A-Za-z0-9_-])(?P<val>\d+(?:\.\d+)?)\s*(?P<unit>A|Amps?|kA|V|Volts?|kV|ms|milliseconds?|Hz|%)?(?![A-Za-z0-9_-])",
        re.IGNORECASE,
    )

    # Standard technical codes and standards to ignore as raw measurements
    EXCLUDED_NUMBERS = {
        "50", "51", "52", "67", "87", "86", "27", "59", "81",  # ANSI device numbers
        "61850", "001", "002", "003", "004", "005", "006",      # Standard / SOP / Rule numbers
        "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",      # List bullet numbers
    }

    @classmethod
    def extract_entities(cls, text: str) -> Set[str]:
        """Extracts all equipment and substation entities present in text."""
        entities: Set[str] = set()
        for pat in cls.ENTITY_PATTERNS:
            for match in pat.finditer(text):
                entities.add(match.group(1).upper().replace("-", "_"))
        return entities

    @classmethod
    def extract_quantities(cls, text: str) -> List[Tuple[float, str]]:
        """Extracts numerical measurements from text, filtering out standard ANSI/rule numbers."""
        quantities: List[Tuple[float, str]] = []
        for match in cls.QUANTITY_PATTERN.finditer(text):
            raw_val = match.group("val")
            raw_unit = (match.group("unit") or "").strip().upper()

            # Normalize units
            if raw_unit in ["AMP", "AMPS"]:
                raw_unit = "A"
            elif raw_unit in ["VOLT", "VOLTS"]:
                raw_unit = "V"
            elif raw_unit == "MILLISECONDS":
                raw_unit = "ms"

            # Skip common ANSI function codes without units
            if not raw_unit and raw_val in cls.EXCLUDED_NUMBERS:
                continue

            try:
                val = float(raw_val)
                # Filter trivial small integers without units unless they represent time
                if not raw_unit and val < 15.0:
                    continue
                quantities.append((val, raw_unit))
            except ValueError:
                continue
        return quantities

    @classmethod
    def verify_faithfulness(cls, narrative, grounding_claims, tolerance_pct=0.5):
        """Only allow complete, verbatim ledger statements plus section labels.

        Entity/quantity bags cannot prove polarity, causality, or binding.
        Free prose that is not covered by the explicit quotation contract falls
        back to the deterministic report; it is not silently called faithful.
        """
        from domain.claims.models import VerificationStatus
        allowed = {c.statement.strip() for c in grounding_claims
                   if c.verification_status in {VerificationStatus.VERIFIED,
                                                VerificationStatus.SUPPORTED_INFERENCE}}
        # Exact full statements may contain multiple sentences. Greedy removal
        # preserves their subject/role/polarity; no token-level substitutions.
        remainder = narrative.strip()
        for statement in sorted(allowed, key=len, reverse=True):
            remainder = remainder.replace(statement, "")
        headings = {"VERIFIED FACTS:", "SUPPORTED INFERENCES:", "RECOMMENDATIONS:",
                    "Evidence:", "Facts:", "Inferences:", "Recommendations:"}
        unknown = [line.strip().lstrip("-* ").strip() for line in remainder.splitlines()
                   if line.strip().lstrip("-* ").strip() not in headings | {""}]
        if unknown:
            diagnostics = ["Unverified prose outside complete ledger quotations: " + line[:512] for line in unknown]
            grounding_text = " ".join(c.statement for c in grounding_claims)
            missing_entities = cls.extract_entities(narrative) - cls.extract_entities(grounding_text)
            if missing_entities:
                diagnostics.append("Ungrounded entity: " + ", ".join(sorted(missing_entities)))
            from services.agent.units import are_quantities_compatible
            ledger_quantities = cls.extract_quantities(grounding_text)
            for value, unit in cls.extract_quantities(narrative):
                if not any(are_quantities_compatible(value, unit, v, u, tolerance_pct=tolerance_pct)[0] for v, u in ledger_quantities):
                    diagnostics.append(f"Ungrounded measurement: {value} {unit}")
            return False, diagnostics
        return bool(allowed) and bool(narrative.strip()), [] if allowed and narrative.strip() else ["Empty grounding or narrative."]
