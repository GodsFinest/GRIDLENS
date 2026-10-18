"""SOETool executing sequence of events and timeline reconciliation."""
from typing import List, Dict, Any, Optional
from domain.models.incident import SOEEvent
from domain.models.results import EventTimelineResult
from services.soe.engine import SOEEngine


class SOETool:
    """Specialized tool for millisecond timeline reconstruction."""

    async def execute(
        self,
        incident_id: str,
        events: Optional[List[Any]] = None,
        comtrade_digital_transitions: Optional[List[Dict[str, Any]]] = None,
        disturbance_t0_ms: Optional[float] = None,
    ) -> EventTimelineResult:
        if events is None:
            import json
            try:
                with open("data/seed/incidents.json", "r", encoding="utf-8") as f:
                    incidents = json.load(f)
                match = next((i for i in incidents if i.get("incident_id") == incident_id), None)
                events = match.get("events", []) if match else []
            except Exception:
                events = []

        result = SOEEngine.build_timeline_from_events(
            incident_id=incident_id,
            raw_events=events,
            comtrade_digital_transitions=comtrade_digital_transitions,
            disturbance_t0_ms=disturbance_t0_ms,
        )
        return result
