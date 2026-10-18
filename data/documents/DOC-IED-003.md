# DOC-IED-003: SIPROTEC 5 - 7SJ85 Relay Configuration & Secondary Wiring Guide

## Section 1: Hardware Architecture & Terminal Layout
The SIPROTEC 5 7SJ85 is a multifunctional overcurrent and feeder protection device. Analog current inputs connect to terminal block X100 (terminals 1 through 8).
- **CH1 (Terminals 1-2)**: Phase A Current ($I_A$)
- **CH2 (Terminals 3-4)**: Phase B Current ($I_B$)
- **CH3 (Terminals 5-6)**: Phase C Current ($I_C$)
- **CH4 (Terminals 7-8)**: Voltage Input ($V_A$)

## Section 2: Channel Mapping & Polarity Verification
> [!CAUTION]
> If secondary CT leads are transposed (e.g. Channel 1 connected to Phase C CT instead of Phase A), the relay will misattribute phase identification in event logs while the actual physical disturbance remains on the crossed phase. Commissioning engineers must verify polarity and point-to-point continuity before energization.

## Section 3: Protection Settings for Feeder F12
- **50P-1 Pickup**: 4000 A (0 ms delay)
- **51P-1 Pickup**: 2500 A (IEEE Very Inverse, Time Dial $TD = 0.10$)
- **50N-1 Pickup**: 600 A
- **Trip Matrix**: Routes logical trip signal from PTOC1 to binary output relay BO1 (Circuit Breaker CB12 trip coil).
