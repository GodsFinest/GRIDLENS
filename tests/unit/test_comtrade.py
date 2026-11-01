"""Unit tests for COMTRADE parser and deterministic signal analyzer."""
import pytest
import os
from services.comtrade.parser import ComtradeParser
from services.comtrade.analyzer import ComtradeSignalAnalyzer


def test_parse_and_analyze_incident_a():
    cfg_path = "data/comtrade/INC-2026-001.CFG"
    dat_path = "data/comtrade/INC-2026-001.DAT"
    assert os.path.exists(cfg_path), "Incident A CFG file must exist."
    assert os.path.exists(dat_path), "Incident A DAT file must exist."

    record = ComtradeParser.parse_files(cfg_path, dat_path)
    assert record.header.station_name == "OGS-01"
    assert record.header.num_analog == 4
    assert record.header.num_digital == 4
    assert len(record.sample_indices) > 0
    assert not record.is_truncated
    assert {b - a for a, b in zip(record.time_microseconds, record.time_microseconds[1:])} == {250.0}

    analysis = ComtradeSignalAnalyzer.analyze_record(record, incident_id="INC-2026-001")

    # Incident A reference measurements.
    # Pre-fault RMS IA/IB/IC in [230, 255] A
    for ch in ["IA", "IB", "IC"]:
        pre_rms = analysis.analog_measurements[ch].pre_fault_rms
        assert 230.0 <= pre_rms <= 255.0, f"Pre-fault {ch} RMS ({pre_rms}) outside [230, 255] A"

    # Fault RMS IC in [3600, 3950] A
    ic_fault = analysis.analog_measurements["IC"].fault_rms
    assert 3600.0 <= ic_fault <= 3950.0, f"Fault IC RMS ({ic_fault}) outside [3600, 3950] A"

    # IA/IB fault RMS < 300 A
    assert analysis.analog_measurements["IA"].fault_rms < 300.0
    assert analysis.analog_measurements["IB"].fault_rms < 300.0

    # Onset within +/- 3 ms of t=0 (t=0 in Incident A is at 40.0 ms in record time)
    assert analysis.onset_time_ms is not None
    assert abs(analysis.onset_time_ms - 40.0) <= 3.0, f"Onset time ({analysis.onset_time_ms}) not within 3 ms of t0 (40.0 ms)"

    # Total clearing time in [40, 70] ms
    assert analysis.total_clearing_time_ms is not None
    assert 40.0 <= analysis.total_clearing_time_ms <= 70.0, f"Clearing time ({analysis.total_clearing_time_ms}) outside [40, 70] ms"

    # Flags
    assert analysis.pickup_exceeded is True
    assert analysis.fault_phase_detected in ["C", "IC"]


def test_incident_b_golden_numerics():
    cfg_path = "data/comtrade/INC-2026-002.CFG"
    dat_path = "data/comtrade/INC-2026-002.DAT"
    assert os.path.exists(cfg_path)
    assert os.path.exists(dat_path)

    record = ComtradeParser.parse_files(cfg_path, dat_path)
    analysis = ComtradeSignalAnalyzer.analyze_record(record, incident_id="INC-2026-002")

    # Fault RMS IC in [3300, 3600] A
    ic_fault = analysis.analog_measurements["IC"].fault_rms
    assert 3300.0 <= ic_fault <= 3600.0, f"Incident B fault IC RMS ({ic_fault}) outside [3300, 3600] A"

    # IA fault RMS < 300 A
    ia_fault = analysis.analog_measurements["IA"].fault_rms
    assert ia_fault < 300.0, f"Incident B fault IA RMS ({ia_fault}) not < 300 A"


def test_incident_c_truncation_detection():
    cfg_path = "data/comtrade/INC-2026-003.CFG"
    dat_path = "data/comtrade/INC-2026-003.DAT"
    assert os.path.exists(cfg_path)

    # This fixture has 0:0 CT metadata in addition to being truncated.
    # Invalid ratios now fail closed before any physical interpretation.
    with pytest.raises(ValueError, match="Positive ratios"):
        ComtradeParser.parse_files(cfg_path, dat_path)
