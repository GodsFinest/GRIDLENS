"""HistoryTool for querying the reproducible seeded incident history."""
import json
from domain.models.results import HistoricalIncidentResult, HistoricalIncidentSummary
from services.config import HISTORY_FILE


class HistoryTool:
    """Specialized tool for querying the three-record in-memory seed history."""

    def __init__(self):
        with HISTORY_FILE.open("r", encoding="utf-8") as history_file:
            seeded_records = json.load(history_file)
        self._history_records = [HistoricalIncidentSummary.model_validate(record) for record in seeded_records]

    async def execute(self, feeder_id: str, limit: int = 3) -> HistoricalIncidentResult:
        matching = [inc for inc in self._history_records if inc.feeder_id == feeder_id.upper()]
        return HistoricalIncidentResult(
            query_feeder_id=feeder_id,
            matching_incidents=matching[:limit],
        )
