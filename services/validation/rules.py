"""Deterministic rule definitions for substation configuration and protection setting validation."""
from typing import Dict, Any, List, Optional
from domain.models.results import ValidationViolation


class ValidationRuleEngine:
    """Deterministic engineering rule checks for substation configurations."""

    @staticmethod
    def check_feeder_primary_relay(feeder_data: Dict[str, Any], relays: Dict[str, Any]) -> Optional[ValidationViolation]:
        feeder_id = feeder_data.get("feeder_id", "UNKNOWN")
        primary_relay_id = feeder_data.get("primary_relay_id")
        if not primary_relay_id or primary_relay_id not in relays:
            return ValidationViolation(
                rule_id="RULE-PROT-001",
                rule_name="feeder_primary_relay_required",
                entity_id=feeder_id,
                entity_type="FEEDER",
                severity="ERROR",
                message=f"Feeder {feeder_id} has no valid primary protection relay configured.",
                remediation_advice=f"Assign an active primary protection relay (e.g. RELAY_12) to {feeder_id}.",
            )
        return None

    @staticmethod
    def check_breaker_association(relay_data: Dict[str, Any], breakers: Dict[str, Any]) -> Optional[ValidationViolation]:
        relay_id = relay_data.get("relay_id", "UNKNOWN")
        breaker_id = relay_data.get("controlled_breaker_id")
        if not breaker_id or breaker_id not in breakers:
            return ValidationViolation(
                rule_id="RULE-PROT-002",
                rule_name="relay_breaker_association_valid",
                entity_id=relay_id,
                entity_type="RELAY",
                severity="ERROR",
                message=f"Relay {relay_id} trip coil is routed to non-existent or invalid breaker '{breaker_id}'.",
                remediation_advice=f"Ensure {relay_id} is associated with a breaker in the same bay.",
            )
        return None

    @staticmethod
    def check_channel_mapping_consistency(
        ied_data: Dict[str, Any],
        sensors: Dict[str, Any],
        bay_id: str
    ) -> List[ValidationViolation]:
        violations = []
        ied_id = ied_data.get("ied_id", "UNKNOWN")
        ct_mapping = ied_data.get("ct_channel_mapping", {})

        # Verify each channel maps to existing sensor and proper phase
        for ch, s_id in ct_mapping.items():
            if s_id not in sensors:
                violations.append(ValidationViolation(
                    rule_id="RULE-MAP-001",
                    rule_name="sensor_channel_mapping_exists",
                    entity_id=ied_id,
                    entity_type="IED",
                    severity="ERROR",
                    message=f"Channel {ch} on {ied_id} maps to non-existent sensor {s_id}.",
                    remediation_advice=f"Update secondary wiring table for channel {ch}.",
                ))
                continue

            s_data = sensors[s_id]
            # Check for phase swapped / inverted mappings (e.g., CH1 expected Phase A, but mapped to Phase C sensor)
            expected_phase = "A" if ch in ["CH1", "IA", "Ch1"] else ("B" if ch in ["CH2", "IB", "Ch2"] else ("C" if ch in ["CH3", "IC", "Ch3"] else ""))
            actual_phase = s_data.get("phase")
            if expected_phase and actual_phase and expected_phase != actual_phase:
                violations.append(ValidationViolation(
                    rule_id="RULE-MAP-003",
                    rule_name="ct_channel_phase_inversion",
                    entity_id=ied_id,
                    entity_type="IED",
                    severity="ERROR",
                    message=f"Channel {ch} expects Phase {expected_phase} CT, but is mapped to {s_id} (Phase {actual_phase}).",
                    remediation_advice=f"Correct secondary terminal block wiring between {s_id} and {ied_id} channel {ch}.",
                ))
        return violations

    @staticmethod
    def check_ct_ratio_validity(sensors: Dict[str, Any]) -> List[ValidationViolation]:
        violations = []
        for s_id, s_data in sensors.items():
            if s_data.get("type") == "CT" or s_id.startswith("CT"):
                primary = float(s_data.get("primary", 0.0))
                secondary = float(s_data.get("secondary", 0.0))
                ratio = float(s_data.get("ratio", 0.0))
                if primary <= 0.0 or secondary <= 0.0 or ratio <= 0.0:
                    violations.append(ValidationViolation(
                        rule_id="RULE-CFG-004",
                        rule_name="ct_ratio_positive_nonzero",
                        entity_id=s_id,
                        entity_type="SENSOR",
                        severity="ERROR",
                        message=f"Current transformer {s_id} has invalid/zero ratio setting (Primary: {primary}, Secondary: {secondary}).",
                        remediation_advice=f"Set calibrated CT ratio (e.g. 1200:5A) in relay parameter block.",
                    ))
        return violations

    @staticmethod
    def check_pickup_threshold_bounds(relay_data: Dict[str, Any], feeder_data: Dict[str, Any]) -> Optional[ValidationViolation]:
        relay_id = relay_data.get("relay_id", "UNKNOWN")
        pickup_a = float(relay_data.get("pickup_current_a", 0.0))
        continuous_a = float(feeder_data.get("rated_continuous_load_a", 630.0))

        if pickup_a <= continuous_a:
            return ValidationViolation(
                rule_id="RULE-SET-005",
                rule_name="pickup_above_rated_load",
                entity_id=relay_id,
                entity_type="RELAY",
                severity="ERROR",
                message=f"Pickup current ({pickup_a} A) is less than or equal to continuous load rating ({continuous_a} A), risking false trips.",
                remediation_advice=f"Increase 51P pickup threshold to at least 1.25x - 1.5x continuous load current.",
            )
        return None
