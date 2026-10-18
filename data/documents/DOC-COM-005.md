# DOC-COM-005: COMTRADE Waveform Interpretation & Oscillography Diagnostic Manual

## Section 1: COMTRADE Standard IEEE C37.111
COMTRADE (Common Format for Transient Data Exchange) files record high-speed analog waveforms and digital event transitions during power system disturbances.
- **CFG File**: Contains channel definitions, sampling rates, scaling factors ($a \cdot x + b$), and trigger timestamps.
- **DAT File**: Contains timestamped raw numerical sample records.

## Section 2: Oscillography Diagnostic Rules
1. **Disturbance Detection**: A sudden step increase in RMS current accompanied by a depression in bus voltage indicates a downstream shunt fault.
2. **True Fault Clearing Time**: Measured from fault inception ($t_0$) until the breaker auxiliary contact (52a) transitions from 1 (closed) to 0 (open) and primary current completely collapses. For standard distribution vacuum breakers, clearing time is typically $45-65\text{ ms}$.
3. **Phase Identification**: The phase exhibiting the highest fault current ($I_{fault} \gg I_{load}$) is the primary faulted conductor. If relay text reports Phase A but waveform shows high current on Phase C, field engineers must investigate secondary channel wiring transpositions.
4. **Data Truncation**: A COMTRADE record with fewer samples than configured in CFG line 13 indicates a relay communication buffer overflow or recorder crash. Such truncated records cannot establish root cause.
