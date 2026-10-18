"""Unit tests for deterministic configuration validator."""
import pytest
from services.validation.validator import ConfigurationValidator
from services.graph.repository import InMemoryGraphRepository


@pytest.mark.asyncio
async def test_normal_configuration_validation():
    repo = InMemoryGraphRepository()
    validator = ConfigurationValidator(repo)

    res = await validator.validate_bay_configuration(bay_id="BAY_F12", feeder_id="F12")
    assert res.valid is True
    assert len(res.violations) == 0


@pytest.mark.asyncio
async def test_phase_inversion_detection():
    repo = InMemoryGraphRepository()
    validator = ConfigurationValidator(repo)

    # Invert Phase A and Phase C CT secondary channel mapping
    swapped_map = {"CH1": "CT12C", "CH2": "CT12B", "CH3": "CT12A"}
    res = await validator.validate_bay_configuration(
        bay_id="BAY_F12",
        feeder_id="F12",
        ied_id="IED_12",
        custom_mapping=swapped_map,
    )
    assert res.valid is False
    assert any(v.rule_id == "RULE-MAP-003" for v in res.violations)
