"""Deterministic configuration validator service for substation protection settings."""
from typing import Dict, Any, List, Optional
from domain.models.results import ValidationResult, ValidationViolation
from services.validation.rules import ValidationRuleEngine
from services.graph.repository import GraphRepository, InMemoryGraphRepository


class ConfigurationValidator:
    """Deterministic validator checking substation configuration consistency."""

    def __init__(self, graph_repo: Optional[GraphRepository] = None):
        self.graph_repo = graph_repo or InMemoryGraphRepository()

    async def validate_bay_configuration(
        self,
        bay_id: str,
        feeder_id: Optional[str] = None,
        ied_id: Optional[str] = None,
        custom_ied_mapping: Optional[Dict[str, str]] = None,
        custom_mapping: Optional[Dict[str, str]] = None,
        custom_sensor_data: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        mapping = custom_ied_mapping or custom_mapping
        topology = await self.graph_repo.get_substation_topology()

        # Normalize collections from list or dict
        feeders = {f["feeder_id"]: f for f in topology.get("feeders", [])} if isinstance(topology.get("feeders"), list) else topology.get("feeders", {})
        relays = {r["relay_id"]: r for r in topology.get("relays", [])} if isinstance(topology.get("relays"), list) else topology.get("relays", {})
        breakers = {b["breaker_id"]: b for b in topology.get("breakers", [])} if isinstance(topology.get("breakers"), list) else topology.get("breakers", {})
        ieds = {i["ied_id"]: i for i in topology.get("ieds", [])} if isinstance(topology.get("ieds"), list) else topology.get("ieds", {})
        if custom_sensor_data:
            sensors = custom_sensor_data
        else:
            raw_s = topology.get("sensors", {})
            sensors = {s["sensor_id"]: s for s in raw_s} if isinstance(raw_s, list) else raw_s

        violations: List[ValidationViolation] = []
        checks_performed = [
            "RULE-PROT-001 (feeder_primary_relay_required)",
            "RULE-PROT-002 (relay_breaker_association_valid)",
            "RULE-MAP-001 (sensor_channel_mapping_exists)",
            "RULE-MAP-003 (ct_channel_phase_inversion)",
            "RULE-CFG-004 (ct_ratio_positive_nonzero)",
            "RULE-SET-005 (pickup_above_rated_load)",
        ]

        target_feeder = None
        if feeder_id and feeder_id.upper() in feeders:
            target_feeder = feeders[feeder_id.upper()]
        elif bay_id:
            for f in feeders.values():
                if f.get("bay_id") == bay_id:
                    target_feeder = f
                    break

        if target_feeder:
            # Check primary relay
            v1 = ValidationRuleEngine.check_feeder_primary_relay(target_feeder, relays)
            if v1:
                violations.append(v1)

            # Check pickup threshold
            r_id = target_feeder.get("primary_relay_id")
            if r_id and r_id in relays:
                v5 = ValidationRuleEngine.check_pickup_threshold_bounds(relays[r_id], target_feeder)
                if v5:
                    violations.append(v5)

        # Check relay breaker associations
        for r_data in relays.values():
            if not bay_id or r_data.get("bay_id") == bay_id:
                v2 = ValidationRuleEngine.check_breaker_association(r_data, breakers)
                if v2:
                    violations.append(v2)

        # Check IED channel mappings
        for i_id, i_data in ieds.items():
            if not ied_id or i_id == ied_id.upper() or i_data.get("bay_id") == bay_id:
                eval_ied = dict(i_data)
                if mapping:
                    eval_ied["ct_channel_mapping"] = mapping
                elif "declared_channel_phase_map" in eval_ied and eval_ied["declared_channel_phase_map"]:
                    eval_ied["ct_channel_mapping"] = eval_ied["declared_channel_phase_map"]
                v_maps = ValidationRuleEngine.check_channel_mapping_consistency(eval_ied, sensors, bay_id)
                violations.extend(v_maps)

        # Check CT ratio validity
        v_ratios = ValidationRuleEngine.check_ct_ratio_validity(sensors)
        violations.extend(v_ratios)

        is_valid = len(violations) == 0

        return ValidationResult(
            target_entity_id=bay_id or feeder_id or ied_id or "SUBSTATION_OGS01",
            valid=is_valid,
            violations=violations,
            checks_performed=checks_performed,
            metadata={"total_violations": len(violations)},
        )
