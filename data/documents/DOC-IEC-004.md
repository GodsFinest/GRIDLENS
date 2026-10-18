# DOC-IEC-004: IEC 61850 Logical Nodes & Data Model Reference (Educational Subset)

## Section 1: Conceptual Architecture
IEC 61850 standardizes substation communications and object models. In this educational reference subset, Substation automation functions are modeled via Logical Nodes (LNs):
- **PIOC (Protection Instantaneous Overcurrent)**: Models non-delayed overcurrent trip elements (ANSI 50).
  - Data Object `Op.general`: Binary trip output.
  - Data Object `Str.general`: Pickup/start status.
- **PTOC (Protection Time Overcurrent)**: Models inverse-time overcurrent elements (ANSI 51).
  - Data Object `TmMult`: Time multiplier setting.
  - Data Object `StrVal`: Pickup current threshold setting.
- **MMXU (Measurement Unit)**: Provides electrical quantities ($V, I, P, Q, f$).
- **XCBR (Circuit Breaker Control & Supervision)**: Models physical breaker mechanism, 52a/52b auxiliary status contacts, and trip counter.
- **CSWI (Switch Controller)**: Coordinates operator command handling and interlocking.
- **TCTR / TVTR**: Interface logical nodes for instrument transformers (CT/VT).

## Section 2: Trip Logic Association
In a valid IEC 61850 engineering configuration, the `Op` output of `PTOC1` must link to `XCBR1.Pos.Oper` within the same Bay container.
