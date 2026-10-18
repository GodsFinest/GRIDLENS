"""ChannelMappingResolver investigating and resolving cross-source discrepancies."""
import itertools
from typing import List, Dict, Any, Optional, Tuple
from domain.evidence.models import Evidence, EvidenceKind
from domain.claims.models import ConflictLifecycle, ConflictTracker, ConflictTransition
from services.validation.validator import ConfigurationValidator


class ChannelMappingResolver:
    """Investigates cross-source discrepancies between relay target flags and physical waveforms."""

    @classmethod
    async def resolve_cross_source_conflict(
        cls,
        evidence_list: List[Evidence],
        bay_id: str,
        validator: ConfigurationValidator,
        conflict_tracker: ConflictTracker,
        declared_mapping: Optional[Dict[str, str]] = None,
        commissioned_mapping: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, Optional[Dict[str, str]], Optional[str]]:
        """
        Evaluates cross-source discrepancy between relay event reports and COMTRADE waveforms.
        If discrepancy exists:
          Transitions: CONFLICT_DETECTED -> INVESTIGATION -> CONFLICT_RESOLVED / CONFLICT_UNRESOLVED.
        Returns:
          (is_resolved: bool, reconciling_mapping: Optional[dict], resolution_rule: Optional[str])
        """
        # 1. Identify relay flagged phase from SOE / apparent cause
        relay_phase: Optional[str] = None
        relay_ev_ids: List[str] = []
        for ev in evidence_list:
            if ev.kind == EvidenceKind.SOE_EVENT:
                fact_upper = ev.fact.upper()
                desc_upper = str(ev.metadata.get("description", "")).upper()
                text = f"{fact_upper} {desc_upper}"
                for p in ["PHASE A", "PHASE B", "PHASE C"]:
                    if p in text:
                        relay_phase = p.split()[-1]
                        relay_ev_ids.append(ev.evidence_id)
                        break
                if relay_phase:
                    break

        # 2. Identify physical waveform surge phase
        waveform_phase: Optional[str] = None
        wav_ev_ids: List[str] = []
        for ev in evidence_list:
            if ev.kind == EvidenceKind.OVERCURRENT_EXCEEDED:
                waveform_phase = ev.metadata.get("fault_phase")
                wav_ev_ids.append(ev.evidence_id)
            elif ev.kind == EvidenceKind.CHANNEL_RMS and waveform_phase is None:
                # Check current channels only (not voltage)
                if ev.unit in ["A", "kA"] and float(ev.structured_value or 0) > 3000.0:
                    waveform_phase = ev.metadata.get("phase")
                    wav_ev_ids.append(ev.evidence_id)

        all_conflict_ev_ids = list(set(relay_ev_ids + wav_ev_ids))

        # Check if discrepancy exists
        has_conflict = False
        if relay_phase and waveform_phase and relay_phase != waveform_phase:
            has_conflict = True
        elif relay_phase and not waveform_phase:
            # Relay asserted trip, but waveform has no fault current on any phase (e.g. INC-2026-004)
            has_conflict = True

        if not has_conflict:
            return True, None, None

        # Discrepancy detected! Transition: NO_CONFLICT -> CONFLICT_DETECTED -> INVESTIGATION
        conflict_tracker.advance_conflict(
            next_state=ConflictLifecycle.CONFLICT_DETECTED,
            rule_id="RULE-CONFLICT-001",
            evidence_ids=all_conflict_ev_ids,
            explanation=(
                f"Discrepancy detected: Relay reported fault on Phase {relay_phase}, "
                f"but waveform oscillography observed {f'Phase {waveform_phase}' if waveform_phase else 'no fault current'}."
            ),
        )

        conflict_tracker.advance_conflict(
            next_state=ConflictLifecycle.INVESTIGATION,
            rule_id="RULE-CONFLICT-INV-001",
            evidence_ids=all_conflict_ev_ids,
            explanation=(
                f"Investigating whether physical CT wiring transposition reconciles "
                f"Phase {relay_phase} relay target with {f'Phase {waveform_phase}' if waveform_phase else 'normal waveform'}."
            ),
        )

        # 3. Generate candidate wiring hypotheses if waveform phase exists
        if not waveform_phase:
            # No fault in oscillography -> cannot be explained by channel transposition
            conflict_tracker.advance_conflict(
                next_state=ConflictLifecycle.CONFLICT_UNRESOLVED,
                rule_id="RULE-CONFLICT-UNRESOLVED",
                evidence_ids=all_conflict_ev_ids,
                explanation="Unresolvable contradiction: Relay flagged trip but oscillography confirms normal balanced load across all phases.",
            )
            return False, None, "RULE-CONFLICT-UNRESOLVED"

        # Channels and physical sensors for this bay
        prefix = "CT12" if "12" in bay_id else "CT13"
        comm_map = commissioned_mapping or {
            "CH1": f"{prefix}A",
            "CH2": f"{prefix}B",
            "CH3": f"{prefix}C",
        }
        sensors = [f"{prefix}A", f"{prefix}B", f"{prefix}C"]
        channels = ["CH1", "CH2", "CH3"]
        phase_to_ch = {"A": "CH1", "B": "CH2", "C": "CH3"}
        target_ch = phase_to_ch.get(relay_phase, "CH1")
        fault_sensor = f"{prefix}{waveform_phase}"

        surviving_candidates: List[Dict[str, Any]] = []

        # Evaluate all 3! = 6 permutations
        for perm in itertools.permutations(sensors):
            candidate_map = {channels[i]: perm[i] for i in range(3)}

            # Does this candidate map route the faulted physical sensor to the relay's reporting channel?
            if candidate_map.get(target_ch) != fault_sensor:
                continue

            # Run validator rules against candidate mapping
            val_res = await validator.validate_bay_configuration(
                bay_id=bay_id,
                custom_mapping=candidate_map,
            )

            # Check if RULE-MAP-003 (ct_channel_phase_inversion) is violated
            has_map_violation = any(v.rule_id == "RULE-MAP-003" for v in val_res.violations)

            # Check if candidate matches declared mapping (if available)
            matches_declared = (declared_mapping is None) or (candidate_map == declared_mapping)

            if has_map_violation and matches_declared:
                surviving_candidates.append({
                    "mapping": candidate_map,
                    "violations": val_res.violations,
                })

        # 4. Assess surviving candidates
        if len(surviving_candidates) == 1:
            winner = surviving_candidates[0]
            winner_map = winner["mapping"]
            conflict_tracker.advance_conflict(
                next_state=ConflictLifecycle.CONFLICT_RESOLVED,
                rule_id="RULE-MAP-003",
                evidence_ids=all_conflict_ev_ids,
                explanation=(
                    f"Conflict resolved by RULE-MAP-003: CT channel inversion detected. "
                    f"Phase {relay_phase} relay target is fed by physical Phase {waveform_phase} sensor ({winner_map.get(target_ch)} on {target_ch})."
                ),
            )
            return True, winner_map, "RULE-MAP-003"
        else:
            conflict_tracker.advance_conflict(
                next_state=ConflictLifecycle.CONFLICT_UNRESOLVED,
                rule_id="RULE-CONFLICT-UNRESOLVED",
                evidence_ids=all_conflict_ev_ids,
                explanation=(
                    f"Unresolvable contradiction: {len(surviving_candidates)} reconciling wiring permutations found "
                    f"between Phase {relay_phase} and Phase {waveform_phase}."
                ),
            )
            return False, None, "RULE-CONFLICT-UNRESOLVED"
