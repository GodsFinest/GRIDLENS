"""Sequence of Events (SOE) engine for millisecond-precision event timeline reconciliation."""
from typing import List, Dict, Any, Optional, Union
from domain.models.incident import SOEEvent
from domain.models.results import EventTimelineResult


class SOEEngine:
    """Authoritative reconciliation engine for sequence-of-events and protection logs."""

    @classmethod
    def build_timeline_from_events(
        cls,
        incident_id: str,
        raw_events: List[Union[SOEEvent, Dict[str, Any]]],
        comtrade_digital_transitions: Optional[List[Dict[str, Any]]] = None,
        disturbance_t0_ms: Optional[float] = None,
    ) -> EventTimelineResult:
        if not raw_events:
            return EventTimelineResult(
                incident_id=incident_id,
                ordered_events=[],
                synchronization_status="UNSYNCHRONIZED",
                anomalies=["No sequence-of-events logs available for this incident."],
            )

        def get_offset(e: Union[SOEEvent, Dict[str, Any]]) -> float:
            if hasattr(e, "offset_ms"):
                return float(e.offset_ms)
            elif isinstance(e, dict):
                return float(e.get("offset_ms", 0.0))
            return 0.0

        def get_field(e: Union[SOEEvent, Dict[str, Any]], field_name: str, default: Any = "") -> Any:
            if hasattr(e, field_name):
                return getattr(e, field_name)
            elif isinstance(e, dict):
                return e.get(field_name, default)
            return default

        t0 = disturbance_t0_ms if disturbance_t0_ms is not None else 40.0

        # Sort raw events chronologically by offset_ms
        sorted_events = sorted(raw_events, key=get_offset)

        # Convert to structured dictionary entries
        ordered_list: List[Dict[str, Any]] = []
        anomalies: List[str] = []

        prev_offset = None
        for ev in sorted_events:
            off_ms = get_offset(ev)
            if prev_offset is not None and (off_ms - prev_offset) > 1000.0:
                ev_id = get_field(ev, "event_id", "EVT")
                anomalies.append(f"Timestamp gap detected: {round(off_ms - prev_offset, 1)} ms before {ev_id}.")

            ordered_list.append({
                "event_id": get_field(ev, "event_id", "EVT"),
                "timestamp": get_field(ev, "timestamp", "00:00:00.000"),
                "offset_ms": off_ms,
                "disturbance_offset_ms": round(off_ms, 2),
                "record_offset_ms": round(off_ms + t0, 2),
                "source_device": get_field(ev, "source_device", "UNKNOWN"),
                "event_type": get_field(ev, "event_type", "EVENT"),
                "channel_or_function": get_field(ev, "channel_or_function", ""),
                "description": get_field(ev, "description", ""),
                "value": get_field(ev, "value", None),
            })
            prev_offset = off_ms

        # Merge COMTRADE digital transitions if present
        if comtrade_digital_transitions:
            for dt in comtrade_digital_transitions:
                rec_off = float(dt["time_ms"])
                dist_off = round(rec_off - t0, 2)
                ordered_list.append({
                    "event_id": f"COMTRADE_DIG_{dt['channel']}_{int(rec_off)}",
                    "timestamp": f"+{dist_off:.1f}ms",
                    "offset_ms": dist_off,
                    "disturbance_offset_ms": dist_off,
                    "record_offset_ms": round(rec_off, 2),
                    "source_device": "COMTRADE_OSCILLOGRAPHY",
                    "event_type": "DIGITAL_EDGE_TRANSITION",
                    "channel_or_function": dt["channel"],
                    "description": f"Digital channel {dt['channel']} changed from {dt['old_val']} to {dt['new_val']}",
                    "value": dt["new_val"],
                })

        # Re-sort combined list monotonically by disturbance_offset_ms
        final_ordered = sorted(ordered_list, key=lambda x: (x["disturbance_offset_ms"], 0 if x["source_device"] != "COMTRADE_OSCILLOGRAPHY" else 1))

        # Check sequence order consistency (e.g. breaker opening before trip or pickup)
        pkp_time = None
        trip_time = None
        for ev in final_ordered:
            etype = str(ev.get("event_type", "")).upper()
            func = str(ev.get("channel_or_function", "")).upper()
            if "PKP" in func or etype == "PICKUP":
                if pkp_time is None:
                    pkp_time = ev["disturbance_offset_ms"]
            elif "TRIP" in func or etype == "TRIP_COMMAND":
                if trip_time is None:
                    trip_time = ev["disturbance_offset_ms"]
            elif "BREAKER_OPEN" in etype or "52A" in func:
                if ev.get("value") in [0, "0", False] or etype == "BREAKER_OPEN":
                    if trip_time is not None and ev["disturbance_offset_ms"] < trip_time:
                        anomalies.append(f"Sequence inversion: Breaker open ({ev['disturbance_offset_ms']} ms) before trip command ({trip_time} ms).")
                    elif pkp_time is not None and ev["disturbance_offset_ms"] < pkp_time:
                        anomalies.append(f"Sequence inversion: Breaker open ({ev['disturbance_offset_ms']} ms) before pickup ({pkp_time} ms).")

        # Calculate total duration in disturbance-relative time base
        total_duration = 0.0
        if len(final_ordered) > 1:
            total_duration = final_ordered[-1]["disturbance_offset_ms"] - final_ordered[0]["disturbance_offset_ms"]

        sync_status = "SYNCHRONIZED"
        if len(anomalies) > 0:
            sync_status = "DESYNCHRONIZED_ANOMALY"

        return EventTimelineResult(
            incident_id=incident_id,
            ordered_events=final_ordered,
            timestamp_precision="1ms",
            synchronization_status=sync_status,
            total_duration_ms=round(total_duration, 2),
            anomalies=anomalies,
        )
