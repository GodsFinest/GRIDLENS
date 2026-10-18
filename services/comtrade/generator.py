"""Synthetic generator for IEEE C37.111-compatible CFG and DAT fixtures for Incidents A, B, and C."""
import os
import numpy as np
from typing import Dict, Any


class ComtradeGenerator:
    """Generates synthetic ASCII COMTRADE-compatible .CFG and .DAT files."""

    @classmethod
    def generate_incident_a_files(cls, output_dir: str) -> Dict[str, str]:
        """Incident A: Genuine Feeder F12 Phase C Overcurrent Fault."""
        os.makedirs(output_dir, exist_ok=True)
        base_name = "INC-2026-001"
        cfg_path = os.path.join(output_dir, f"{base_name}.CFG")
        dat_path = os.path.join(output_dir, f"{base_name}.DAT")

        sample_rate = 4000.0  # Hz (80 samples/cycle @ 50Hz)
        nominal_freq = 50.0
        total_time_s = 0.200  # 200 ms total
        total_samples = int(sample_rate * total_time_s)
        time_s = np.linspace(-0.040, total_time_s - 0.040, total_samples)
        time_us = (time_s + 0.040) * 1e6
        time_ms = (time_s + 0.040) * 1e3

        # Physics signals:
        # Pre-fault (t < 0): Ia=240A RMS, Ib=240A RMS, Ic=240A RMS, Va=6350V RMS
        # Fault (0 <= t < 0.055): Ic jumps to 3850A RMS with DC offset, Va dips to 2100V RMS
        # Cleared (t >= 0.055): Breaker opens, Ia, Ib, Ic collapse to 0
        w = 2 * np.pi * nominal_freq

        ia = np.zeros(total_samples)
        ib = np.zeros(total_samples)
        ic = np.zeros(total_samples)
        va = np.zeros(total_samples)

        d_50p_pkp = np.zeros(total_samples, dtype=int)
        d_51p_trip = np.zeros(total_samples, dtype=int)
        d_52a_brk = np.ones(total_samples, dtype=int)   # 1 = closed, 0 = open
        d_52b_brk = np.zeros(total_samples, dtype=int)  # 0 = closed, 1 = open

        for i, t in enumerate(time_s):
            if t < 0.0:
                # Pre-fault normal load
                ia[i] = 240.0 * np.sqrt(2) * np.sin(w * t)
                ib[i] = 240.0 * np.sqrt(2) * np.sin(w * t - 2*np.pi/3)
                ic[i] = 240.0 * np.sqrt(2) * np.sin(w * t + 2*np.pi/3)
                va[i] = 6350.0 * np.sqrt(2) * np.sin(w * t)
            elif t < 0.055:
                # Fault duration
                decay = np.exp(-t / 0.030)  # DC offset decaying with 30ms time constant
                ia[i] = 240.0 * np.sqrt(2) * np.sin(w * t)
                ib[i] = 240.0 * np.sqrt(2) * np.sin(w * t - 2*np.pi/3)
                # Phase C severe overcurrent (3850 A RMS)
                ic[i] = 3850.0 * np.sqrt(2) * np.sin(w * t + 2*np.pi/3) + (1600.0 * decay)
                va[i] = 2100.0 * np.sqrt(2) * np.sin(w * t)  # Voltage depression

                if t >= 0.014:
                    d_50p_pkp[i] = 1
                if t >= 0.020:
                    d_51p_trip[i] = 1
            else:
                # Fault cleared, breaker opened
                d_50p_pkp[i] = 1 if t < 0.080 else 0
                d_51p_trip[i] = 1 if t < 0.100 else 0
                d_52a_brk[i] = 0  # Opened
                d_52b_brk[i] = 1
                # Small residual decaying arc until 0.072s
                if t < 0.072:
                    arc_decay = np.exp(-(t - 0.055) / 0.005)
                    ia[i] = 20.0 * arc_decay * np.sin(w * t)
                    ic[i] = 250.0 * arc_decay * np.sin(w * t + 2*np.pi/3)
                else:
                    ia[i] = 0.0
                    ib[i] = 0.0
                    ic[i] = 0.0
                va[i] = 6350.0 * np.sqrt(2) * np.sin(w * t)  # Bus voltage restored

        # Write CFG
        cfg_lines = [
            f"OGS-01,RELAY_12,2013",
            f"8,4A,4D",
            f"1,IA,A,BAY_F12,A,1.0,0.0,0.0,-50000,50000,1200,5,P",
            f"2,IB,B,BAY_F12,A,1.0,0.0,0.0,-50000,50000,1200,5,P",
            f"3,IC,C,BAY_F12,A,1.0,0.0,0.0,-50000,50000,1200,5,P",
            f"4,VA,A,BAY_F12,V,1.0,0.0,0.0,-50000,50000,11000,110,P",
            f"1,50P_PKP,,,0",
            f"2,51P_TRIP,,,0",
            f"3,52A_BRK,,,1",
            f"4,52B_BRK,,,0",
            f"50.0",
            f"1",
            f"{sample_rate},{total_samples}",
            f"2026-09-02 14:32:16.960000",
            f"2026-09-02 14:32:17.000000",
            f"ASCII",
            f"1.0",
        ]
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write("\n".join(cfg_lines) + "\n")

        # Write DAT
        dat_lines = []
        for i in range(total_samples):
            dat_lines.append(
                f"{i+1},{int(time_us[i])},"
                f"{ia[i]:.2f},{ib[i]:.2f},{ic[i]:.2f},{va[i]:.2f},"
                f"{d_50p_pkp[i]},{d_51p_trip[i]},{d_52a_brk[i]},{d_52b_brk[i]}"
            )
        with open(dat_path, "w", encoding="utf-8") as f:
            f.write("\n".join(dat_lines) + "\n")

        return {"cfg": cfg_path, "dat": dat_path}

    @classmethod
    def generate_incident_b_files(cls, output_dir: str) -> Dict[str, str]:
        """Incident B: Misleading Channel Mapping Inconsistency (Relay event logs Phase A, but CT Phase C waveform has fault)."""
        os.makedirs(output_dir, exist_ok=True)
        base_name = "INC-2026-002"
        cfg_path = os.path.join(output_dir, f"{base_name}.CFG")
        dat_path = os.path.join(output_dir, f"{base_name}.DAT")

        sample_rate = 4000.0
        nominal_freq = 50.0
        total_time_s = 0.200
        total_samples = int(sample_rate * total_time_s)
        time_s = np.linspace(-0.040, total_time_s - 0.040, total_samples)
        time_us = (time_s + 0.040) * 1e6
        w = 2 * np.pi * nominal_freq

        ia = np.zeros(total_samples)
        ib = np.zeros(total_samples)
        ic = np.zeros(total_samples)
        va = np.zeros(total_samples)

        d_50p_pkp = np.zeros(total_samples, dtype=int)
        d_51p_trip = np.zeros(total_samples, dtype=int)
        d_52a_brk = np.ones(total_samples, dtype=int)
        d_52b_brk = np.zeros(total_samples, dtype=int)

        for i, t in enumerate(time_s):
            if t < 0.0:
                ia[i] = 238.0 * np.sqrt(2) * np.sin(w * t)
                ib[i] = 240.0 * np.sqrt(2) * np.sin(w * t - 2*np.pi/3)
                ic[i] = 241.0 * np.sqrt(2) * np.sin(w * t + 2*np.pi/3)
                va[i] = 6350.0 * np.sqrt(2) * np.sin(w * t)
            elif t < 0.058:
                decay = np.exp(-t / 0.028)
                # Phase A is NORMAL (238 A)
                ia[i] = 238.0 * np.sqrt(2) * np.sin(w * t)
                ib[i] = 240.0 * np.sqrt(2) * np.sin(w * t - 2*np.pi/3)
                # Phase C is ABNORMAL (3450 A RMS)
                ic[i] = 3450.0 * np.sqrt(2) * np.sin(w * t + 2*np.pi/3) + (1400.0 * decay)
                va[i] = 2400.0 * np.sqrt(2) * np.sin(w * t)

                if t >= 0.015:
                    d_50p_pkp[i] = 1
                if t >= 0.022:
                    d_51p_trip[i] = 1
            else:
                d_50p_pkp[i] = 0
                d_51p_trip[i] = 0
                d_52a_brk[i] = 0
                d_52b_brk[i] = 1
                ia[i] = 0.0
                ib[i] = 0.0
                ic[i] = 0.0
                va[i] = 6350.0 * np.sqrt(2) * np.sin(w * t)

        # In Incident B CFG, note channel mapping: Channel 1 is mapped to CT12C (swapped during commissioning)
        cfg_lines = [
            f"OGS-01,RELAY_12,2013",
            f"8,4A,4D",
            f"1,IA,A,BAY_F12,A,1.0,0.0,0.0,-50000,50000,1200,5,P",
            f"2,IB,B,BAY_F12,A,1.0,0.0,0.0,-50000,50000,1200,5,P",
            f"3,IC,C,BAY_F12,A,1.0,0.0,0.0,-50000,50000,1200,5,P",
            f"4,VA,A,BAY_F12,V,1.0,0.0,0.0,-50000,50000,11000,110,P",
            f"1,50P_PKP,,,0",
            f"2,51P_TRIP,,,0",
            f"3,52A_BRK,,,1",
            f"4,52B_BRK,,,0",
            f"50.0",
            f"1",
            f"{sample_rate},{total_samples}",
            f"2026-09-02 10:15:21.960000",
            f"2026-09-02 10:15:22.000000",
            f"ASCII",
            f"1.0",
        ]
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write("\n".join(cfg_lines) + "\n")

        dat_lines = []
        for i in range(total_samples):
            dat_lines.append(
                f"{i+1},{int(time_us[i])},"
                f"{ia[i]:.2f},{ib[i]:.2f},{ic[i]:.2f},{va[i]:.2f},"
                f"{d_50p_pkp[i]},{d_51p_trip[i]},{d_52a_brk[i]},{d_52b_brk[i]}"
            )
        with open(dat_path, "w", encoding="utf-8") as f:
            f.write("\n".join(dat_lines) + "\n")

        return {"cfg": cfg_path, "dat": dat_path}

    @classmethod
    def generate_incident_c_files(cls, output_dir: str) -> Dict[str, str]:
        """Incident C: Insufficient Evidence (Truncated COMTRADE recording after 1.5 cycles, missing channel ratio)."""
        os.makedirs(output_dir, exist_ok=True)
        base_name = "INC-2026-003"
        cfg_path = os.path.join(output_dir, f"{base_name}.CFG")
        dat_path = os.path.join(output_dir, f"{base_name}.DAT")

        sample_rate = 4000.0
        total_samples = 120  # Only 30 ms (120 samples) recorded before memory buffer error!
        time_s = np.linspace(-0.015, 0.015, total_samples)
        time_us = (time_s + 0.015) * 1e6
        w = 2 * np.pi * 50.0

        ia = np.zeros(total_samples)
        ib = np.zeros(total_samples)
        ic = np.zeros(total_samples)
        va = np.zeros(total_samples)

        d_50p_pkp = np.zeros(total_samples, dtype=int)
        d_51p_trip = np.zeros(total_samples, dtype=int)
        d_52a_brk = np.ones(total_samples, dtype=int)
        d_52b_brk = np.zeros(total_samples, dtype=int)

        for i, t in enumerate(time_s):
            if t < 0.0:
                ia[i] = 180.0 * np.sqrt(2) * np.sin(w * t)
                ib[i] = 180.0 * np.sqrt(2) * np.sin(w * t - 2*np.pi/3)
                ic[i] = 180.0 * np.sqrt(2) * np.sin(w * t + 2*np.pi/3)
                va[i] = 6350.0 * np.sqrt(2) * np.sin(w * t)
            else:
                # Sudden transient jump but recording cuts off immediately at +15ms
                ia[i] = 180.0 * np.sqrt(2) * np.sin(w * t)
                ib[i] = 180.0 * np.sqrt(2) * np.sin(w * t - 2*np.pi/3)
                ic[i] = 2900.0 * np.sqrt(2) * np.sin(w * t + 2*np.pi/3)
                va[i] = 4200.0 * np.sqrt(2) * np.sin(w * t)
                if t >= 0.010:
                    d_50p_pkp[i] = 1

        cfg_lines = [
            f"OGS-01,RELAY_13,2013",
            f"8,4A,4D",
            f"1,IA,A,BAY_F13,A,1.0,0.0,0.0,-50000,50000,0,0,P",  # Missing CT ratio (0/0)
            f"2,IB,B,BAY_F13,A,1.0,0.0,0.0,-50000,50000,0,0,P",
            f"3,IC,C,BAY_F13,A,1.0,0.0,0.0,-50000,50000,0,0,P",
            f"4,VA,A,BAY_F13,V,1.0,0.0,0.0,-50000,50000,11000,110,P",
            f"1,50P_PKP,,,0",
            f"2,51P_TRIP,,,0",
            f"3,52A_BRK,,,1",
            f"4,52B_BRK,,,0",
            f"50.0",
            f"1",
            f"{sample_rate},800",  # Expected 800 samples (200ms), but only 120 provided -> Truncated!
            f"2026-09-02 09:14:59.985000",
            f"2026-09-02 09:15:00.000000",
            f"ASCII",
            f"1.0",
        ]
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write("\n".join(cfg_lines) + "\n")

        dat_lines = []
        for i in range(total_samples):
            dat_lines.append(
                f"{i+1},{int(time_us[i])},"
                f"{ia[i]:.2f},{ib[i]:.2f},{ic[i]:.2f},{va[i]:.2f},"
                f"{d_50p_pkp[i]},{d_51p_trip[i]},{d_52a_brk[i]},{d_52b_brk[i]}"
            )
        with open(dat_path, "w", encoding="utf-8") as f:
            f.write("\n".join(dat_lines) + "\n")

        return {"cfg": cfg_path, "dat": dat_path}

    @classmethod
    def generate_incident_d_files(cls, output_dir: str) -> Dict[str, str]:
        """Incident D (INC-2026-004): Unresolvable Cross-Source Contradiction.
        Waveform shows normal steady load (240A on all phases), but relay log asserts trip."""
        os.makedirs(output_dir, exist_ok=True)
        base_name = "INC-2026-004"
        cfg_path = os.path.join(output_dir, f"{base_name}.CFG")
        dat_path = os.path.join(output_dir, f"{base_name}.DAT")

        sample_rate = 4000.0
        total_time_s = 0.200
        total_samples = int(sample_rate * total_time_s)
        time_s = np.linspace(-0.040, total_time_s - 0.040, total_samples)
        time_us = (time_s + 0.040) * 1e6
        w = 2 * np.pi * 50.0

        ia = np.zeros(total_samples)
        ib = np.zeros(total_samples)
        ic = np.zeros(total_samples)
        va = np.zeros(total_samples)

        d_50p_pkp = np.zeros(total_samples, dtype=int)
        d_51p_trip = np.zeros(total_samples, dtype=int)
        d_52a_brk = np.ones(total_samples, dtype=int)
        d_52b_brk = np.zeros(total_samples, dtype=int)

        # Entire record is normal 240A load (no fault in oscillography)
        for i, t in enumerate(time_s):
            ia[i] = 240.0 * np.sqrt(2) * np.sin(w * t)
            ib[i] = 240.0 * np.sqrt(2) * np.sin(w * t - 2*np.pi/3)
            ic[i] = 240.0 * np.sqrt(2) * np.sin(w * t + 2*np.pi/3)
            va[i] = 6350.0 * np.sqrt(2) * np.sin(w * t)

        cfg_lines = [
            f"OGS-01,RELAY_12,2013",
            f"8,4A,4D",
            f"1,IA,A,BAY_F12,A,1.0,0.0,0.0,-50000,50000,1200,5,P",
            f"2,IB,B,BAY_F12,A,1.0,0.0,0.0,-50000,50000,1200,5,P",
            f"3,IC,C,BAY_F12,A,1.0,0.0,0.0,-50000,50000,1200,5,P",
            f"4,VA,A,BAY_F12,V,1.0,0.0,0.0,-50000,50000,11000,110,P",
            f"1,50P_PKP,,,0",
            f"2,51P_TRIP,,,0",
            f"3,52A_BRK,,,1",
            f"4,52B_BRK,,,0",
            f"50.0",
            f"1",
            f"{sample_rate},{total_samples}",
            f"2026-09-02 11:20:00.000000",
            f"2026-09-02 11:20:00.040000",
            f"ASCII",
            f"1.0",
        ]
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write("\n".join(cfg_lines) + "\n")

        dat_lines = []
        for i in range(total_samples):
            dat_lines.append(
                f"{i+1},{int(time_us[i])},"
                f"{ia[i]:.2f},{ib[i]:.2f},{ic[i]:.2f},{va[i]:.2f},"
                f"{d_50p_pkp[i]},{d_51p_trip[i]},{d_52a_brk[i]},{d_52b_brk[i]}"
            )
        with open(dat_path, "w", encoding="utf-8") as f:
            f.write("\n".join(dat_lines) + "\n")

        return {"cfg": cfg_path, "dat": dat_path}

    @classmethod
    def generate_incident_e_files(cls, output_dir: str) -> Dict[str, str]:
        """Incident E (INC-2026-005): Settings Misoperation (Load surge to 550A on 630A cable, relay set to 500A)."""
        os.makedirs(output_dir, exist_ok=True)
        base_name = "INC-2026-005"
        cfg_path = os.path.join(output_dir, f"{base_name}.CFG")
        dat_path = os.path.join(output_dir, f"{base_name}.DAT")

        sample_rate = 4000.0
        total_time_s = 0.200
        total_samples = int(sample_rate * total_time_s)
        time_s = np.linspace(-0.040, total_time_s - 0.040, total_samples)
        time_us = (time_s + 0.040) * 1e6
        w = 2 * np.pi * 50.0

        ia = np.zeros(total_samples)
        ib = np.zeros(total_samples)
        ic = np.zeros(total_samples)
        va = np.zeros(total_samples)

        d_50p_pkp = np.zeros(total_samples, dtype=int)
        d_51p_trip = np.zeros(total_samples, dtype=int)
        d_52a_brk = np.ones(total_samples, dtype=int)
        d_52b_brk = np.zeros(total_samples, dtype=int)

        for i, t in enumerate(time_s):
            if t < 0.0:
                ia[i] = 240.0 * np.sqrt(2) * np.sin(w * t)
                ib[i] = 240.0 * np.sqrt(2) * np.sin(w * t - 2*np.pi/3)
                ic[i] = 240.0 * np.sqrt(2) * np.sin(w * t + 2*np.pi/3)
                va[i] = 6350.0 * np.sqrt(2) * np.sin(w * t)
            elif t < 0.055:
                # Load step to 550 A (within cable rating 630A, but trips relay set to 500A)
                ia[i] = 550.0 * np.sqrt(2) * np.sin(w * t)
                ib[i] = 550.0 * np.sqrt(2) * np.sin(w * t - 2*np.pi/3)
                ic[i] = 550.0 * np.sqrt(2) * np.sin(w * t + 2*np.pi/3)
                va[i] = 6200.0 * np.sqrt(2) * np.sin(w * t)
                if t >= 0.015:
                    d_50p_pkp[i] = 1
                if t >= 0.022:
                    d_51p_trip[i] = 1
            else:
                d_52a_brk[i] = 0
                d_52b_brk[i] = 1

        cfg_lines = [
            f"OGS-01,RELAY_12,2013",
            f"8,4A,4D",
            f"1,IA,A,BAY_F12,A,1.0,0.0,0.0,-50000,50000,1200,5,P",
            f"2,IB,B,BAY_F12,A,1.0,0.0,0.0,-50000,50000,1200,5,P",
            f"3,IC,C,BAY_F12,A,1.0,0.0,0.0,-50000,50000,1200,5,P",
            f"4,VA,A,BAY_F12,V,1.0,0.0,0.0,-50000,50000,11000,110,P",
            f"1,50P_PKP,,,0",
            f"2,51P_TRIP,,,0",
            f"3,52A_BRK,,,1",
            f"4,52B_BRK,,,0",
            f"50.0",
            f"1",
            f"{sample_rate},{total_samples}",
            f"2026-09-02 16:45:00.000000",
            f"2026-09-02 16:45:00.040000",
            f"ASCII",
            f"1.0",
        ]
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write("\n".join(cfg_lines) + "\n")

        dat_lines = []
        for i in range(total_samples):
            dat_lines.append(
                f"{i+1},{int(time_us[i])},"
                f"{ia[i]:.2f},{ib[i]:.2f},{ic[i]:.2f},{va[i]:.2f},"
                f"{d_50p_pkp[i]},{d_51p_trip[i]},{d_52a_brk[i]},{d_52b_brk[i]}"
            )
        with open(dat_path, "w", encoding="utf-8") as f:
            f.write("\n".join(dat_lines) + "\n")

        return {"cfg": cfg_path, "dat": dat_path}
