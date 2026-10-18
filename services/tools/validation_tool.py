"""ValidationTool executing deterministic configuration consistency checks."""
from typing import Optional, Dict, Any
from domain.models.results import ValidationResult
from services.validation.validator import ConfigurationValidator
from services.graph.repository import GraphRepository


class ValidationTool:
    """Specialized tool for deterministic configuration validation."""

    def __init__(self, validator: Optional[ConfigurationValidator] = None, graph_repo: Optional[GraphRepository] = None):
        self.validator = validator or ConfigurationValidator(graph_repo)

    async def execute(
        self,
        bay_id: str = "BAY_F12",
        feeder_id: Optional[str] = None,
        ied_id: Optional[str] = None,
        custom_mapping: Optional[Dict[str, str]] = None,
    ) -> ValidationResult:
        result = await self.validator.validate_bay_configuration(
            bay_id=bay_id,
            feeder_id=feeder_id,
            ied_id=ied_id,
            custom_ied_mapping=custom_mapping,
        )
        return result
