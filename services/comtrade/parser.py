"""COMTRADE (IEEE C37.111 / IEC 60255-24) parser for ASCII CFG and DAT files."""
import os
import math
from typing import Dict, List, Any, Tuple
from pydantic import BaseModel, Field


class AnalogChannelHeader(BaseModel):
    index: int
    name: str
    phase: str
    circuit_component: str
    units: str
    multiplier: float
    offset: float
    skew: float
    min_val: float
    max_val: float
    primary_ratio: float
    secondary_ratio: float
    scaling_type: str = "P"  # "P" for primary, "S" for secondary


class DigitalChannelHeader(BaseModel):
    index: int
    name: str
    phase: str
    circuit_component: str
    normal_state: int = 0


class ComtradeHeader(BaseModel):
    station_name: str
    device_name: str
    version_year: str = "2013"
    total_channels: int
    num_analog: int
    num_digital: int
    analog_channels: List[AnalogChannelHeader] = Field(default_factory=list)
    digital_channels: List[DigitalChannelHeader] = Field(default_factory=list)
    nominal_frequency: float = 50.0
    sampling_rates: List[Tuple[float, int]] = Field(default_factory=list)  # (rate_hz, end_sample)
    start_timestamp: str = ""
    trigger_timestamp: str = ""
    data_format: str = "ASCII"
    timestamp_multiplier: float = 1.0  # Microseconds


class ComtradeRecord(BaseModel):
    header: ComtradeHeader
    sample_indices: List[int] = Field(default_factory=list)
    time_microseconds: List[float] = Field(default_factory=list)
    time_milliseconds: List[float] = Field(default_factory=list)
    analog_data: Dict[str, List[float]] = Field(default_factory=dict)  # Channel Name -> list of primary values
    digital_data: Dict[str, List[int]] = Field(default_factory=dict)   # Channel Name -> list of 0/1 bits
    is_truncated: bool = False
    normalization: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class ComtradeParser:
    """Deterministic parser for IEEE C37.111 COMTRADE CFG and DAT files."""

    @classmethod
    def parse_files(cls, cfg_path: str, dat_path: str) -> ComtradeRecord:
        if not os.path.exists(cfg_path):
            raise FileNotFoundError(f"COMTRADE CFG file not found at: {cfg_path}")
        if not os.path.exists(dat_path):
            raise FileNotFoundError(f"COMTRADE DAT file not found at: {dat_path}")

        with open(cfg_path, "r", encoding="utf-8", errors="replace") as f:
            cfg_content = f.read()

        with open(dat_path, "r", encoding="utf-8", errors="replace") as f:
            dat_content = f.read()

        header = cls.parse_cfg(cfg_content)
        record = cls.parse_dat(dat_content, header)
        return record

    @classmethod
    def parse_cfg(cls, cfg_text: str) -> ComtradeHeader:
        lines = [line.strip() for line in cfg_text.strip().splitlines() if line.strip()]
        if len(lines) < 5:
            raise ValueError(f"Malformed COMTRADE CFG file. Expected at least 5 lines, got {len(lines)}")

        # Line 1: Station, Device, Version
        line1 = [p.strip() for p in lines[0].split(",")]
        station_name = line1[0] if len(line1) > 0 else "UNKNOWN"
        device_name = line1[1] if len(line1) > 1 else "RELAY"
        version_year = line1[2] if len(line1) > 2 else "2013"
        if len(line1) != 3 or version_year not in {"1999", "2013"}:
            raise ValueError("Explicit 1999/2013 COMTRADE revision is required")

        # Line 2: Total channels, num analog (A), num digital (D)
        line2 = [p.strip() for p in lines[1].split(",")]
        total_ch = int(line2[0])
        num_analog = int(line2[1].rstrip("A").strip())
        num_digital = int(line2[2].rstrip("D").strip())

        curr_line = 2
        analog_channels: List[AnalogChannelHeader] = []
        for i in range(num_analog):
            parts = [p.strip() for p in lines[curr_line].split(",")]
            if len(parts) != 13:
                raise ValueError("Analog headers must explicitly provide unit, scaling and transformer ratios")
            ch = AnalogChannelHeader(
                index=int(parts[0]),
                name=parts[1],
                phase=parts[2] if len(parts) > 2 else "",
                circuit_component=parts[3] if len(parts) > 3 else "",
                units=parts[4] if len(parts) > 4 else "A",
                multiplier=float(parts[5]) if len(parts) > 5 else 1.0,
                offset=float(parts[6]) if len(parts) > 6 else 0.0,
                skew=float(parts[7]) if len(parts) > 7 else 0.0,
                min_val=float(parts[8]) if len(parts) > 8 else -99999.0,
                max_val=float(parts[9]) if len(parts) > 9 else 99999.0,
                primary_ratio=float(parts[10]) if len(parts) > 10 else 1.0,
                secondary_ratio=float(parts[11]) if len(parts) > 11 else 1.0,
                scaling_type=parts[12] if len(parts) > 12 else "P",
            )
            analog_channels.append(ch)
            curr_line += 1

        digital_channels: List[DigitalChannelHeader] = []
        for i in range(num_digital):
            parts = [p.strip() for p in lines[curr_line].split(",")]
            d_ch = DigitalChannelHeader(
                index=int(parts[0]),
                name=parts[1],
                phase=parts[2] if len(parts) > 2 else "",
                circuit_component=parts[3] if len(parts) > 3 else "",
                normal_state=int(parts[4]) if len(parts) > 4 else 0,
            )
            digital_channels.append(d_ch)
            curr_line += 1

        # Nominal frequency
        nominal_freq = float(lines[curr_line].split(",")[0])
        curr_line += 1

        # Sampling rates
        num_rates = int(lines[curr_line].split(",")[0])
        curr_line += 1
        sampling_rates = []
        for _ in range(num_rates):
            parts = [p.strip() for p in lines[curr_line].split(",")]
            sampling_rates.append((float(parts[0]), int(parts[1])))
            curr_line += 1

        # Timestamps
        start_ts = lines[curr_line] if curr_line < len(lines) else ""
        curr_line += 1
        trigger_ts = lines[curr_line] if curr_line < len(lines) else ""
        curr_line += 1

        # Format and multiplier
        data_format = lines[curr_line] if curr_line < len(lines) else "ASCII"
        curr_line += 1
        time_mult = float(lines[curr_line]) if curr_line < len(lines) else 1.0

        header = ComtradeHeader(
            station_name=station_name,
            device_name=device_name,
            version_year=version_year,
            total_channels=total_ch,
            num_analog=num_analog,
            num_digital=num_digital,
            analog_channels=analog_channels,
            digital_channels=digital_channels,
            nominal_frequency=nominal_freq,
            sampling_rates=sampling_rates,
            start_timestamp=start_ts,
            trigger_timestamp=trigger_ts,
            data_format=data_format,
            timestamp_multiplier=time_mult,
        )
        cls.validate_header(header)
        return header

    @staticmethod
    def validate_header(header):
        """Supported subset: ASCII, one fixed sampling rate, zero channel skew.

        Unsupported metadata is rejected, not interpreted as a default format.
        Current/voltage values become primary SI units before any thresholds.
        """
        if header.data_format.upper() != "ASCII":
            raise ValueError("Only ASCII COMTRADE is supported")
        if (len(header.sampling_rates) != 1 or header.sampling_rates[0][0] <= 0 or
                not math.isfinite(header.sampling_rates[0][0]) or header.sampling_rates[0][1] <= 0):
            raise ValueError("Exactly one positive fixed sampling rate is required")
        if header.total_channels != header.num_analog + header.num_digital:
            raise ValueError("Channel counts do not agree")
        if header.num_analog != len(header.analog_channels) or header.num_digital != len(header.digital_channels):
            raise ValueError("Channel header count mismatch")
        names = [c.name for c in header.analog_channels + header.digital_channels]
        if len(set(names)) != len(names):
            raise ValueError("Duplicate channel names")
        if (not math.isfinite(header.nominal_frequency) or header.nominal_frequency <= 0 or
                not math.isfinite(header.timestamp_multiplier) or header.timestamp_multiplier <= 0):
            raise ValueError("Invalid frequency/time multiplier")
        for ch in header.analog_channels:
            values = (ch.multiplier, ch.offset, ch.primary_ratio, ch.secondary_ratio, ch.skew)
            if not all(math.isfinite(v) for v in values):
                raise ValueError("Non-finite channel metadata")
            if ch.units not in {"A", "kA", "V", "kV"} or ch.scaling_type not in {"P", "S"}:
                raise ValueError("Unsupported analog unit or primary/secondary designation")
            if ch.primary_ratio <= 0 or ch.secondary_ratio <= 0 or ch.skew != 0:
                raise ValueError("Positive ratios and zero channel skew are required")

    @classmethod
    def parse_dat(cls, dat_text: str, header: ComtradeHeader) -> ComtradeRecord:
        cls.validate_header(header)
        header = header.model_copy(deep=True)
        normalization = {}
        factors = {}
        for ch in header.analog_channels:
            factor = (1000.0 if ch.units.startswith("k") else 1.0)
            if ch.scaling_type == "S":
                factor *= ch.primary_ratio / ch.secondary_ratio
            factors[ch.name] = factor
            normalization[ch.name] = {"source_unit": ch.units, "source_scaling": ch.scaling_type,
                                      "primary_ratio": ch.primary_ratio, "secondary_ratio": ch.secondary_ratio,
                                      "to_primary_si_factor": factor, "multiplier": ch.multiplier, "offset": ch.offset}
            ch.units = ch.units.removeprefix("k")
            ch.scaling_type = "P"
        lines = [line.strip() for line in dat_text.strip().splitlines() if line.strip()]

        sample_indices: List[int] = []
        time_us: List[float] = []
        time_ms: List[float] = []

        analog_data: Dict[str, List[float]] = {ch.name: [] for ch in header.analog_channels}
        digital_data: Dict[str, List[int]] = {d.name: [] for d in header.digital_channels}

        for line_idx, line in enumerate(lines):
            tokens = [t.strip() for t in line.split(",")]
            expected_tokens = 2 + header.num_analog + header.num_digital
            if len(tokens) != expected_tokens:
                raise ValueError(f"Malformed DAT row {line_idx + 1}: expected {expected_tokens} fields")

            s_idx = int(tokens[0])
            t_val = float(tokens[1]) * header.timestamp_multiplier
            if s_idx != line_idx + 1 or not math.isfinite(t_val) or t_val < 0:
                raise ValueError("DAT indices must be contiguous from 1 and timestamps finite/nonnegative")
            if time_us and t_val <= time_us[-1]:
                raise ValueError("DAT timestamps must increase")
            if time_us:
                period = 1e6 / header.sampling_rates[0][0]
                if abs((t_val - time_us[-1]) - period) > max(1.01 * header.timestamp_multiplier, period * 0.01):
                    raise ValueError("DAT timestamps disagree with configured fixed sample rate")
            sample_indices.append(s_idx)
            time_us.append(t_val)
            time_ms.append(t_val / 1000.0)

            # Parse analog values
            ptr = 2
            for ch in header.analog_channels:
                raw_val = float(tokens[ptr])
                # Physical value = a * raw + b
                scaled_val = ((ch.multiplier * raw_val) + ch.offset) * factors[ch.name]
                if not math.isfinite(scaled_val):
                    raise ValueError("Non-finite analog sample")
                analog_data[ch.name].append(scaled_val)
                ptr += 1

            # Parse digital bits
            for d_ch in header.digital_channels:
                bit_val = int(tokens[ptr])
                if bit_val not in (0, 1):
                    raise ValueError("Digital samples must be 0 or 1")
                digital_data[d_ch.name].append(bit_val)
                ptr += 1

        # Detect truncation: if total recorded samples < expected end sample
        expected_samples = header.sampling_rates[0][1] if header.sampling_rates else 800
        if not sample_indices or len(sample_indices) > expected_samples:
            raise ValueError("Empty DAT or sample count exceeds CFG declaration")
        is_truncated = len(sample_indices) < expected_samples

        return ComtradeRecord(
            header=header,
            sample_indices=sample_indices,
            time_microseconds=time_us,
            time_milliseconds=time_ms,
            analog_data=analog_data,
            digital_data=digital_data,
            is_truncated=is_truncated,
            normalization=normalization,
        )
