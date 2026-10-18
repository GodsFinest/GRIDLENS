# DOC-SUB-002: Orion Grid Substation OGS-01 Single-Line & Bay Operating Manual

## Section 1: Substation Topology & Bus Architecture
Orion Grid Substation OGS-01 is an urban distribution substation stepping down 33 kV grid transmission to 11 kV regional distribution.
- **33 kV Bus A**: Receives power from transmission grid via line disconnectors.
- **Power Transformer T1**: 33/11 kV, 25 MVA, Dyn11 vector group, 8.5% impedance.
- **11 kV Bus B**: Feeds outgoing distribution radial feeders F12 and F13.

## Section 2: Bay F12 (North Industrial Feeder) Configuration
- **Feeder ID**: F12
- **Nominal Voltage**: 11 kV (6.35 kV Phase-to-Ground)
- **Continuous Rated Load**: 630 A
- **Circuit Breaker**: CB12 (Vacuum Circuit Breaker, 2000 A rated, 25 kA breaking capacity, 55 ms clearing time).
- **Protection Relay**: RELAY_12 (SIPROTEC 5 7SJ85 running in IED_12).
- **Instrument Transformers**:
  - CT12A, CT12B, CT12C: Ratio 1200:5 A (Factor: 240.0), Class 0.2S, connected to IED_12 Channels 1, 2, and 3.
  - VT12: Ratio 11000:110 V (Factor: 100.0), connected to IED_12 Channel 4.

## Section 3: Bay F13 (South Commercial Feeder) Configuration
- **Feeder ID**: F13
- **Nominal Voltage**: 11 kV
- **Continuous Rated Load**: 400 A
- **Circuit Breaker**: CB13 (Vacuum Circuit Breaker, 2000 A rated).
- **Protection Relay**: RELAY_13 (SIPROTEC 5 7SJ85 in IED_13).
- **Instrument Transformers**: CT13A, CT13B, CT13C (Ratio 1200:5 A), VT13 (11000:110 V).
