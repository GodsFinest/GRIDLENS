"""Unit tests for Sequence of Events (SOE) engine and time-base unification."""
import json
from services.soe.engine import SOEEngine
from services.comtrade.parser import ComtradeParser
from services.comtrade.analyzer import ComtradeSignalAnalyzer


def test_incident_a_merged_timeline_golden():
    # Load Incident A seed events
    with open("data/seed/incidents.json", "r", encoding="utf-8") as f:
        incidents = json.load(f)
    inc_a = next(i for i in incidents if i["incident_id"] == "INC-2026-001")

    # Parse and analyze COMTRADE for digital transitions
    record = ComtradeParser.parse_files("data/comtrade/INC-2026-001.CFG", "data/comtrade/INC-2026-001.DAT")
    analysis = ComtradeSignalAnalyzer.analyze_record(record, incident_id="INC-2026-001")

    # Build merged timeline
    timeline = SOEEngine.build_timeline_from_events(
        incident_id="INC-2026-001",
        raw_events=inc_a["events"],
        comtrade_digital_transitions=analysis.digital_transitions,
        disturbance_t0_ms=analysis.onset_time_ms or 40.0,
    )

    # 1. Monotonic ordering by disturbance_offset_ms
    offsets = [e["disturbance_offset_ms"] for e in timeline.ordered_events]
    assert offsets == sorted(offsets), "Merged timeline events must be monotonically ordered"

    # 2. Both disturbance_offset_ms and record_offset_ms are present on every event
    for e in timeline.ordered_events:
        assert "disturbance_offset_ms" in e
        assert "record_offset_ms" in e
        assert isinstance(e["disturbance_offset_ms"], (int, float))
        assert isinstance(e["record_offset_ms"], (int, float))

    # 3. Find specific transitions:
    # 50P_PKP 0->1 edge at disturbance_offset 14 ms (+/- 3)
    pkp_events = [
        e for e in timeline.ordered_events
        if ("50P" in e["channel_or_function"] or "51P_PKP" in e["channel_or_function"])
        and (e.get("value") == 1 or e["event_type"] == "PICKUP")
    ]
    assert len(pkp_events) > 0, "Pickup event must be present"
    for ev in pkp_events:
        assert abs(ev["disturbance_offset_ms"] - 14.0) <= 3.0, f"50P_PKP offset ({ev['disturbance_offset_ms']}) not within 3 ms of 14 ms"

    # 51P_TRIP at ~20 ms (+/- 3)
    trip_events = [
        e for e in timeline.ordered_events
        if "51P_TRIP" in e["channel_or_function"]
        and (e.get("value") == 1 or e["event_type"] == "TRIP_COMMAND")
    ]
    assert len(trip_events) > 0, "Trip event must be present"
    for ev in trip_events:
        assert abs(ev["disturbance_offset_ms"] - 20.0) <= 3.0, f"51P_TRIP offset ({ev['disturbance_offset_ms']}) not within 3 ms of 20 ms"

    # 52A open at ~55 ms (+/- 3)
    brk_open_events = [
        e for e in timeline.ordered_events
        if "52A" in e["channel_or_function"]
        and (e.get("value") == 0 or e["event_type"] == "BREAKER_OPEN")
    ]
    assert len(brk_open_events) > 0, "52A breaker open event must be present"
    for ev in brk_open_events:
        assert abs(ev["disturbance_offset_ms"] - 55.0) <= 3.0, f"52A open offset ({ev['disturbance_offset_ms']}) not within 3 ms of 55 ms"

    # 4. Synchronization status must be SYNCHRONIZED
    assert timeline.synchronization_status == "SYNCHRONIZED"
    assert len(timeline.anomalies) == 0

    # 5. Total duration must be in disturbance-relative time
    assert timeline.total_duration_ms is not None
    assert 50.0 <= timeline.total_duration_ms <= 110.0
