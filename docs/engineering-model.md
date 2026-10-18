# Orion Grid Substation OGS-01 & IEC 61850 Educational Subset Model

## 1. Substation OGS-01 Single-Line Architecture
Orion Grid Substation OGS-01 is a synthetic 33/11 kV distribution substation modeled with physical and logical realism:

- **33 kV Transmission Bus A**: Infeed from regional grid.
- **Power Transformer T1**: 33/11 kV, 25 MVA, Dyn11 vector group, 8.5% impedance.
- **11 kV Distribution Bus B**: Radial distribution bus feeding feeder bays.
- **Bay F12 (North Industrial Feeder)**:
  - Feeder ID: `F12` (11 kV underground cable, 630 A rated load).
  - Breaker: `CB12` (Vacuum circuit breaker, 2000 A rated, 25 kA breaking capacity).
  - Primary Protection Relay: `RELAY_12` (SIPROTEC 5 7SJ85).
  - Current Transformers: `CT12A`, `CT12B`, `CT12C` (1200:5 A ratio).
  - Voltage Transformer: `VT12` (11000:110 V ratio).
- **Bay F13 (South Commercial Feeder)**:
  - Feeder ID: `F13` (11 kV mixed overhead/underground, 400 A rated load).
  - Breaker: `CB13`, Relay: `RELAY_13`, Sensors: `CT13A/B/C`, `VT13`.

---

## 2. IEC 61850-Inspired Conceptual Model (Educational Subset)

> [!NOTE]
> GridLens implements an **educational/synthetic subset** of the IEC 61850 data model to provide meaningful structural graph reasoning. It does not claim full certification compliance with the entire international standard.

### Logical Node (LN) Hierarchy:
- **`PIOC1` (Protection Instantaneous Overcurrent)**: ANSI 50 non-delayed element.
- **`PTOC1` (Protection Time Overcurrent)**: ANSI 51 inverse-time element with configurable time dial.
- **`MMXU1` (Measurement Unit)**: 3-phase voltage, current, and active/reactive power measurements.
- **`XCBR1` (Circuit Breaker Supervision)**: Models breaker auxiliary contacts (52a/52b) and operating counter.
- **`CSWI1` (Switch Controller)**: Handles simulated operator commands and interlocking.
- **`TCTR1..3` / `TVTR1`**: Current and voltage transformer instrument interfaces.

### Valid Association Rules:
1. `PTOC1.Op.general` trip output routes to `XCBR1.Pos.Oper` binary trip coil.
2. `TCTR` channel mappings must match physical secondary CT phase wiring without transposed terminals.
