"""Fail-closed quotations, bound measurements, and executable inference rules.

Not general natural-language entailment. Unsupported paraphrases are rejected.
The provenance and correctness of the tool evidence remain trust assumptions.
"""
import re
from domain.claims.models import ClaimType, VerificationStatus as V
from domain.evidence.models import EvidenceKind as K
from services.agent.inference_rules import derive, render, RECOMMENDATIONS


class ClaimVerifier:
    NUMERICAL_PATTERN = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>kA|A|Amps?|kV|V|Volts?|ms|milliseconds?|Hz|%)?\b", re.I)
    EQUIPMENT_TOKEN_PATTERN = re.compile(r"\b(?:CB|RELAY|IED)[_\s-]*\d+|\bBUS[_\s-]*[A-Z]+|\bCT[_\s-]*\d+\s*[A-Z]?", re.I)

    @classmethod
    def extract_quantities(cls, text):
        return [(float(m['value']), (m['unit'] or '').upper()) for m in cls.NUMERICAL_PATTERN.finditer(text)
                if m['unit'] or float(m['value']) >= 100]

    @staticmethod
    def canonicalize_entity_token(token):
        return re.sub(r"[^A-Z0-9]", "", token.upper())

    @classmethod
    def extract_equipment_tokens(cls, text):
        return [cls.canonicalize_entity_token(m.group()) for m in cls.EQUIPMENT_TOKEN_PATTERN.finditer(text or "")]

    @classmethod
    def ledger_equipment_set(cls, evidence_list):
        return {t for e in evidence_list for t in cls.extract_equipment_tokens(e.fact + " " + str(e.structured_value))}

    @staticmethod
    def compute_text_similarity(a, b):
        """Display/search diagnostic only; NEVER a verification criterion."""
        x, y = set(re.findall(r"\w+", a.lower())), set(re.findall(r"\w+", b.lower()))
        return len(x & y) / max(1, len(x | y))

    @staticmethod
    def _bound_measurement(statement, ev, tolerance):
        # Full-match grammar binds subject, role and quantity; no extra clauses.
        patterns = (
            r"Phase ([ABC]) fault(?:-window)? RMS current (?:was|is|=) ([0-9]+(?:\.[0-9]+)?) (A|kA)\.",
            r"Phase ([ABC]) fault current (?:was|is|=) ([0-9]+(?:\.[0-9]+)?) (A|kA)\.",
        )
        if ev.kind != K.CHANNEL_RMS or type(ev.structured_value) not in (int, float):
            return False
        for pattern in patterns:
            m = re.fullmatch(pattern, statement)
            if m and m[1] == str(ev.metadata.get('phase', '')).removeprefix('I'):
                from services.agent.units import are_quantities_compatible
                return are_quantities_compatible(float(m[2]), m[3], ev.structured_value, ev.unit or '', tolerance_pct=tolerance)[0]
        return False

    @staticmethod
    def _template_match(statement, ev, tolerance):
        """Finite grammar: bind every quantity and apparatus to its source role.

        Conversion of units is allowed only when the entire surrounding text
        is identical. Other supported surface forms are explicitly rendered
        from a fully matched source template, never scored by word overlap.
        """
        from services.agent.units import are_quantities_compatible
        pattern = re.compile(r"([0-9]+(?:\.[0-9]+)?) (kA|A|kV|V|ms|s|Hz)\b")
        a, b = list(pattern.finditer(statement)), list(pattern.finditer(ev.fact))
        if a and len(a) == len(b) and pattern.sub("<quantity>", statement) == pattern.sub("<quantity>", ev.fact):
            return all(are_quantities_compatible(float(x[1]), x[2], float(y[1]), y[2], tolerance_pct=tolerance)[0] for x, y in zip(a, b))
        forms = set()
        m = re.fullmatch(r"(RELAY[_-]\d+) is configured as the primary protection relay for Feeder (F\d+)\.", ev.fact)
        if m:
            relay, feeder = m.groups()
            forms.update((f"Primary protection relay for Feeder {feeder} is configured as {relay}.",
                          f"Feeder {feeder} is protected by {relay} as its primary protection relay.",
                          f"{relay} serves as the configured primary protection relay for Feeder {feeder}.",
                          f"Feeder {feeder} has primary protection relay configured as {relay}."))
        m = re.fullmatch(r"Feeder (F\d+) is controlled by circuit breaker (CB\d+) on (BUS_[A-Z0-9]+)\.", ev.fact)
        if m:
            feeder, breaker, bus = m.groups()
            forms.update((f"Circuit breaker {breaker} controls Feeder {feeder} on {bus}.",
                          f"On {bus}, Feeder {feeder} is controlled by circuit breaker {breaker}."))
        m = re.fullmatch(r"Channel (I[ABC]) measured Pre-fault RMS: ([0-9.]+) A, Fault RMS: ([0-9.]+) A \(Peak: ([0-9.]+) A\)\.", ev.fact)
        if m:
            channel, pre, fault, peak = m.groups()
            forms.update((f"Pre-fault current of {pre} A and fault current of {fault} A was measured on Channel {channel}.",
                          f"Channel {channel} registered a {fault} A fault RMS after {pre} A pre-fault operation.",
                          f"Channel {channel} recorded {pre} A pre-fault and {fault} A during the Phase {channel[-1]} fault.",
                          f"Peak current reached {peak} A with fault RMS of {fault} A on Channel {channel}."))
        m = re.fullmatch(r"Total fault clearing time was ([0-9.]+) ms\.", ev.fact)
        if m:
            forms.update((f"Fault clearing time was measured at {m[1]} ms.",
                          f"The total time to clear the fault was {m[1]} ms.",
                          f"Total fault clearing duration reached {m[1]} ms."))
        return statement in forms

    @classmethod
    def verify_candidate_claims(cls, candidate_claims, evidence_list,
                                numerical_tolerance_percent=0.5, similarity_threshold=0.70):
        ledger = {e.evidence_id: e for e in evidence_list}
        ids = [c.claim_id for c in candidate_claims]
        ambiguous = len(ledger) != len(evidence_list) or len(set(ids)) != len(ids)
        facts, inferences, rejected = [], [], []
        for c in candidate_claims:
            c.verification_status = V.UNVERIFIED
        # Never trust caller-supplied status. Verify facts before inference.
        for c in sorted(candidate_claims, key=lambda c: c.claim_type == ClaimType.INFERENCE):
            cited = [ledger[eid] for eid in c.evidence_ids if eid in ledger]
            ok = not ambiguous
            notes = "Rejected: unsupported statement, missing/ambiguous citations, or failed executable rule."
            if c.claim_type == ClaimType.FACT:
                ok = ok and len(c.evidence_ids) == len(cited) == 1
                if ok:
                    ev = cited[0]
                    if ev.kind == K.DOC_CHUNK:
                        content = ev.metadata.get('full_content', ev.fact)
                        sentences = re.split(r'(?<=[.!?])\s+|\n+', content.strip())
                        ok = bool(c.statement.strip()) and c.statement in sentences
                    else:
                        ok = (c.statement == ev.fact or cls._bound_measurement(c.statement, ev, numerical_tolerance_percent)
                              or cls._template_match(c.statement, ev, numerical_tolerance_percent))
                        if not ok:
                            from services.agent.derived import DerivedQuantityCrossChecker
                            derived = DerivedQuantityCrossChecker.check_derived_claim(c, ledger, numerical_tolerance_percent)
                            ok = derived is not None and derived[0]
                status = V.VERIFIED
                if ok:
                    notes = "Source-bound quotation/measurement; source correctness is not independently certified."
            elif c.claim_type == ClaimType.INFERENCE:
                by_id = {f.claim_id: f for f in facts if f.claim_type == ClaimType.FACT}
                premises = [by_id.get(cid) for cid in c.premise_claim_ids]
                ok = ok and bool(premises) and all(premises) and len(set(c.evidence_ids)) == len(c.evidence_ids)
                if ok:
                    premise_eids = {eid for p in premises for eid in p.evidence_ids}
                    ok = premise_eids == set(c.evidence_ids) and len(cited) == len(c.evidence_ids)
                result = derive(c.inference_rule_id, cited) if ok else None
                ok = ok and result is not None and result == c.inference_result and c.statement == render(c.inference_rule_id, result)
                status = V.SUPPORTED_INFERENCE
                if ok:
                    notes = "Conclusion recomputed from exactly the cited, verified premises."
            else:
                ok = ok and c.statement in RECOMMENDATIONS and not c.evidence_ids
                status = V.VERIFIED
                if ok:
                    notes = "Allowlisted review guidance; not a fact or authorization for field action."
            c.verification_status = status if ok else V.REJECTED
            if not ok and cited:
                ungrounded = set(cls.extract_equipment_tokens(c.statement)) - cls.ledger_equipment_set(cited)
                if ungrounded:
                    notes += " Statement references ungrounded equipment: " + ", ".join(sorted(ungrounded))
                notes += " Numerical assertion mismatch or unsupported binding/grammar: " + c.statement
                if (any(unit in {"V", "KV"} for _, unit in cls.extract_quantities(c.statement)) and cited[0].unit == "A" or
                        any(unit in {"A", "KA"} for _, unit in cls.extract_quantities(c.statement)) and cited[0].unit == "V"):
                    notes += " Incompatible physical dimensions."
            c.verification_notes = notes
            (inferences if ok and c.claim_type == ClaimType.INFERENCE else facts if ok else rejected).append(c)
        return facts, inferences, rejected

    verify_claims = verify_candidate_claims
