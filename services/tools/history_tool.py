"""HistoryTool for querying historical incident records."""
from typing import List
from domain.models.results import HistoricalIncidentResult, HistoricalIncidentSummary


class HistoryTool:
    """Specialized tool for historical incident archive querying."""

    def __init__(self):
        self._history_db = [
            HistoricalIncidentSummary(
                incident_id="INC-2025-089",
                timestamp="2025-11-14T14:10:00Z",
                feeder_id="F12",
                fault_type="Phase C to Ground Overcurrent",
                root_cause="Tree branch contact with 11kV overhead line section during wind storm.",
                clearing_time_ms=56.0,
                similarity_factors=["Overcurrent > 3500 A", "Phase C", "ANSI 51 trip"],
            ),
            HistoricalIncidentSummary(
                incident_id="INC-2025-034",
                timestamp="2025-04-10T08:22:00Z",
                feeder_id="F12",
                fault_type="3-Phase Short Circuit",
                root_cause="Underground cable splice insulation breakdown.",
                clearing_time_ms=52.0,
                similarity_factors=["Instantaneous ANSI 50 trip", "High symmetrical current"],
            ),
            HistoricalIncidentSummary(
                incident_id="INC-2024-012",
                timestamp="2024-08-22T11:45:00Z",
                feeder_id="F12",
                fault_type="Misleading Phase Flagging",
                root_cause="Inverted secondary wiring between Phase A and Phase C CT test blocks.",
                clearing_time_ms=58.0,
                similarity_factors=["Phase A relay event vs Phase C waveform anomaly", "Secondary CT inversion"],
            ),
        ]

    async def execute(self, feeder_id: str, limit: int = 3) -> HistoricalIncidentResult:
        matching = [inc for inc in self._history_db if inc.feeder_id == feeder_id.upper()]
        return HistoricalIncidentResult(
            query_feeder_id=feeder_id,
            matching_incidents=matching[:limit],
        )
