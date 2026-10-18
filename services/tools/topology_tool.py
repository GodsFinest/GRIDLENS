"""TopologyTool executing deterministic graph queries against substation topology repository."""
from typing import Optional, Dict, Any
from domain.models.results import TopologyQueryResult
from services.graph.repository import GraphRepository, InMemoryGraphRepository


class TopologyTool:
    """Specialized tool for deterministic substation topology facts."""

    def __init__(self, graph_repo: Optional[GraphRepository] = None):
        self.graph_repo = graph_repo or InMemoryGraphRepository()

    async def execute(self, feeder_id: str, bay_id: Optional[str] = None) -> TopologyQueryResult:
        result = await self.graph_repo.get_feeder_protection_chain(feeder_id)
        return result

    async def get_relationships(self, equipment_id: str) -> Dict[str, Any]:
        return await self.graph_repo.get_equipment_relationships(equipment_id)
