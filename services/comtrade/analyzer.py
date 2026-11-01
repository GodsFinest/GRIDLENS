"""Deterministic signal analyzer for COMTRADE recordings (IEEE C37.111 / IEC 60255-24)."""
import numpy as np
from typing import Dict, List, Optional, Any
from domain.models.results import ComtradeAnalysisResult, ChannelMeasurement
from services.comtrade.parser import ComtradeRecord


class ComtradeSignalAnalyzer:
    """Deterministic, mathematical analysis of COMTRADE waveforms."""

    @classmethod
    def analyze_record(
        cls,
        record: ComtradeRecord,
        incident_id: str,
        pickup_threshold_a: float = 2500.0,
        nominal_freq: Optional[float] = None,
    ) -> ComtradeAnalysisResult:
        if not record.time_milliseconds or not record.analog_data:
            return ComtradeAnalysisResult(
                incident_id=incident_id,
                sample_rate_hz=record.header.sampling_rates[0][0] if record.header.sampling_rates else 4000.0,
                total_samples=len(record.sample_indices),
                duration_ms=0.0,
                is_truncated=True,
                analysis_notes=["Empty or corrupted waveform recording."],
            )

        nominal_freq = record.header.nominal_frequency if nominal_freq is None else nominal_freq
        if not np.isfinite(pickup_threshold_a) or pickup_threshold_a <= 0 or not np.isfinite(nominal_freq) or nominal_freq <= 0:
            raise ValueError("Positive finite pickup threshold and frequency required")
        t_ms = np.array(record.time_milliseconds)
        duration_ms = float(t_ms[-1] - t_ms[0]) if len(t_ms) > 1 else 0.0
        sample_rate = float(record.header.sampling_rates[0][0]) if record.header.sampling_rates else 4000.0
        samples_per_cycle = int(round(sample_rate / nominal_freq)) if nominal_freq > 0 else 80

        # Identify disturbance start and transition points from digital flags or derivative
        pickup_time_ms: Optional[float] = None
        trip_time_ms: Optional[float] = None
        breaker_open_ms: Optional[float] = None
        digital_transitions: List[Dict[str, Any]] = []

        # Parse digital channels for standard relay bit flags: 50P_PKP, 51P_TRIP, 52A_BRK, 52B_BRK
        for d_name, bits in record.digital_data.items():
            b_arr = np.array(bits)
            diffs = np.diff(b_arr)
            transitions = np.where(diffs != 0)[0]
            for idx in transitions:
                trans_time = float(t_ms[idx + 1])
                old_val = int(b_arr[idx])
                new_val = int(b_arr[idx + 1])
                digital_transitions.append({
                    "channel": d_name,
                    "time_ms": trans_time,
                    "old_val": old_val,
                    "new_val": new_val,
                })

                d_upper = d_name.upper()
                if "PKP" in d_upper or "PICKUP" in d_upper or "50P" in d_upper or "51P_PKP" in d_upper:
                    if new_val == 1 and pickup_time_ms is None:
                        pickup_time_ms = trans_time
                elif "TRIP" in d_upper or "51P_TRIP" in d_upper or "TRP" in d_upper:
                    if new_val == 1 and trip_time_ms is None:
                        trip_time_ms = trans_time
                elif "52B" in d_upper:
                    if new_val == 1 and breaker_open_ms is None:
                        breaker_open_ms = trans_time
                elif "52A" in d_upper or "BREAKER" in d_upper or "BRK" in d_upper:
                    if new_val == 0 and breaker_open_ms is None:  # 52A transitions to 0 when breaker opens
                        breaker_open_ms = trans_time

        # Disturbance start: locate where pickup occurred or standard 40ms pre-fault split
        # Principled Disturbance-Onset Detection:
        # 1. Compute sliding-window RMS per analog channel (window = one nominal cycle, hop = 1 sample)
        # 2. Baseline per channel = median sliding RMS over first two cycles of the record (guaranteed pre-fault in seeded files)
        # 3. disturbance_onset_sample = first sample where ANY current channel's sliding RMS >= max(2.0 * baseline, baseline + pickup_threshold_a * 0.25)
        # 4. Pre-fault RMS measured on one-cycle window ENDING one full cycle BEFORE onset (never overlapping the fault)
        # 5. Fault window starts at onset; ends at breaker-open edge (52A -> 0) if present else record end.

        window_size = samples_per_cycle if samples_per_cycle > 0 else 80
        disturbance_onset_sample: Optional[int] = None
        onset_time_ms: Optional[float] = None

        current_channel_names = [
            ch.name for ch in record.header.analog_channels
            if ch.units.upper() in ["A", "AMPS", "KA"] or ch.name.upper().startswith("I")
        ]

        if len(t_ms) >= window_size and current_channel_names:
            candidate_onsets = []
            kernel = np.ones(window_size) / window_size

            for ch_name in current_channel_names:
                vals = np.array(record.analog_data.get(ch_name, []))
                if len(vals) < window_size:
                    continue
                sq = vals ** 2
                sliding_rms = np.sqrt(np.convolve(sq, kernel, mode="valid"))

                # Baseline: median over first two cycles (if available)
                baseline_samples_count = min(len(sliding_rms), window_size)
                baseline_rms = float(np.median(sliding_rms[:baseline_samples_count])) if baseline_samples_count > 0 else 0.0

                threshold = max(2.0 * baseline_rms, baseline_rms + pickup_threshold_a * 0.25)
                exceeded_indices = np.where(sliding_rms >= threshold)[0]
                if len(exceeded_indices) > 0:
                    first_onset_sample = int(exceeded_indices[0] + window_size - 1)
                    candidate_onsets.append(first_onset_sample)

            if candidate_onsets:
                disturbance_onset_sample = min(candidate_onsets)
                onset_time_ms = round(float(t_ms[disturbance_onset_sample]), 2)

        # Pre-fault window: one-cycle window ending one full cycle BEFORE onset
        pre_fault_window_ms: Optional[List[float]] = None
        if disturbance_onset_sample is not None and disturbance_onset_sample >= 2 * window_size:
            pre_end_idx = disturbance_onset_sample - window_size
            pre_start_idx = pre_end_idx - window_size
            pre_fault_window_ms = [round(float(t_ms[pre_start_idx]), 2), round(float(t_ms[pre_end_idx]), 2)]
        elif disturbance_onset_sample is not None and disturbance_onset_sample >= window_size:
            pre_end_idx = disturbance_onset_sample
            pre_start_idx = max(0, pre_end_idx - window_size)
            pre_fault_window_ms = [round(float(t_ms[pre_start_idx]), 2), round(float(t_ms[pre_end_idx]), 2)]
        else:
            pre_start_idx = 0
            pre_end_idx = min(len(t_ms), window_size)
            if len(t_ms) > 0:
                pre_fault_window_ms = [round(float(t_ms[0]), 2), round(float(t_ms[min(len(t_ms) - 1, window_size)]), 2)]

        # Fault window: starts at onset (or 0 if no onset); ends at breaker-open edge if present, else record end
        fault_start_idx = disturbance_onset_sample if disturbance_onset_sample is not None else 0
        end_fault_idx = len(t_ms)
        if breaker_open_ms is not None:
            brk_idxs = np.where(t_ms >= breaker_open_ms)[0]
            if len(brk_idxs) > 0:
                end_fault_idx = brk_idxs[0]
        # RMS over an integral number of nominal cycles avoids phase-dependent
        # bias from arbitrary partial-cycle endpoints. Short records retain a
        # partial window and must not be treated as a steady-state estimate.
        whole_cycles = (end_fault_idx - fault_start_idx) // window_size
        rms_end_idx = fault_start_idx + whole_cycles * window_size if whole_cycles else end_fault_idx

        analog_measurements: Dict[str, ChannelMeasurement] = {}
        max_fault_current = 0.0
        fault_phase_detected: Optional[str] = None
        pickup_exceeded = False

        for ch in record.header.analog_channels:
            raw_vals = np.array(record.analog_data.get(ch.name, []))
            if len(raw_vals) == 0:
                continue

            # Pure pre-fault window
            pre_window = raw_vals[pre_start_idx:pre_end_idx] if pre_end_idx > pre_start_idx else raw_vals[:window_size]
            pre_rms = cls._calculate_rms(pre_window)

            # Pure active fault window
            fault_window = raw_vals[fault_start_idx:rms_end_idx] if rms_end_idx > fault_start_idx else raw_vals[fault_start_idx:]
            fault_rms = cls._calculate_rms(fault_window) if len(fault_window) > 0 else pre_rms
            peak_val = float(np.max(np.abs(fault_window))) if len(fault_window) > 0 else float(np.max(np.abs(raw_vals)))
            delta_val = float(fault_rms - pre_rms)

            measurement = ChannelMeasurement(
                channel_name=ch.name,
                phase=ch.phase,
                pre_fault_rms=round(pre_rms, 2),
                fault_rms=round(fault_rms, 2),
                peak_value=round(peak_val, 2),
                delta_value=round(delta_val, 2),
                unit=ch.units,
                normalization=record.normalization.get(ch.name, {}),
            )
            analog_measurements[ch.name] = measurement

            # Check if this is a current channel and exceeds pickup
            if ch.units.upper() in ["A", "AMPS", "KA"] or ch.name.upper().startswith("I"):
                if fault_rms > max_fault_current:
                    max_fault_current = fault_rms
                    fault_phase_detected = ch.phase if ch.phase else ch.name

                if fault_rms >= pickup_threshold_a:
                    pickup_exceeded = True

        # Calculate clearing time: only if breaker actually opened
        total_clearing_time_ms: Optional[float] = None
        if breaker_open_ms is not None:
            if onset_time_ms is not None and breaker_open_ms >= onset_time_ms:
                total_clearing_time_ms = round(breaker_open_ms - onset_time_ms, 2)
            elif pickup_time_ms is not None and breaker_open_ms >= pickup_time_ms:
                total_clearing_time_ms = round(breaker_open_ms - pickup_time_ms, 2)

        freq_est = cls._estimate_frequency(record, sample_rate)

        notes: List[str] = []
        if record.is_truncated:
            notes.append("WARNING: DAT contains fewer samples than declared in CFG; the missing interval is unknown.")
        if pickup_exceeded:
            notes.append(f"Overcurrent threshold ({pickup_threshold_a} A) exceeded on {fault_phase_detected} (Fault RMS: {round(max_fault_current, 1)} A).")
        if total_clearing_time_ms:
            notes.append(f"Estimated onset/pickup-to-breaker-contact interval: {total_clearing_time_ms} ms. Contact indication does not prove electrical clearance.")

        return ComtradeAnalysisResult(
            incident_id=incident_id,
            sample_rate_hz=sample_rate,
            total_samples=len(record.sample_indices),
            duration_ms=round(duration_ms, 2),
            is_truncated=record.is_truncated,
            analog_measurements=analog_measurements,
            frequency_hz=round(freq_est, 2) if freq_est else None,
            fault_phase_detected=fault_phase_detected,
            pickup_threshold_a=pickup_threshold_a,
            pickup_exceeded=pickup_exceeded,
            onset_time_ms=onset_time_ms,
            pre_fault_window_ms=pre_fault_window_ms,
            pickup_time_ms=pickup_time_ms,
            trip_time_ms=trip_time_ms,
            breaker_open_time_ms=breaker_open_ms,
            total_clearing_time_ms=total_clearing_time_ms,
            digital_transitions=digital_transitions,
            analysis_notes=notes,
        )

    @staticmethod
    def _calculate_rms(signal: np.ndarray) -> float:
        if len(signal) == 0:
            return 0.0
        return float(np.sqrt(np.mean(signal ** 2)))

    @staticmethod
    def _estimate_frequency(record: ComtradeRecord, sample_rate: float) -> Optional[float]:
        for ch_name, data in record.analog_data.items():
            arr = np.array(data)
            if len(arr) < 100 or np.max(np.abs(arr)) < 1.0:
                continue
            zero_crossings = np.where(np.diff(np.sign(arr)))[0]
            if len(zero_crossings) >= 4:
                half_periods = np.diff(zero_crossings)
                avg_half_period = np.median(half_periods)
                if avg_half_period > 0:
                    period_samples = avg_half_period * 2
                    return float(sample_rate / period_samples)
        return None
