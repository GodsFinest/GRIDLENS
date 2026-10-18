# COMTRADE Standard (IEEE C37.111 / IEC 60255-24) Architecture

## 1. Supported Format Specification
GridLens supports the explicit 1999/2013 ASCII `.CFG`/`.DAT` subset described in [verification.md](verification.md): one fixed sample rate, zero skew, positive transformer ratios and A/kA/V/kV units. This is not a claim of full standard conformance.

### Configuration (`.CFG`) Structure
```
Station_Name,Device_Name,2013
8,4A,4D
1,IA,A,BAY_F12,A,1.0,0.0,0.0,-50000,50000,1200,5,P
2,IB,B,BAY_F12,A,1.0,0.0,0.0,-50000,50000,1200,5,P
3,IC,C,BAY_F12,A,1.0,0.0,0.0,-50000,50000,1200,5,P
4,VA,A,BAY_F12,V,1.0,0.0,0.0,-50000,50000,11000,110,P
1,50P_PKP,,,0
2,51P_TRIP,,,0
3,52A_BRK,,,1
4,52B_BRK,,,0
50.0
1
4000.0,800
2026-09-02 14:32:16.960000
2026-09-02 14:32:17.000000
ASCII
1.0
```

---

## 2. Deterministic Signal Analysis Algorithms

The deterministic signal analyzer (`services/comtrade/analyzer.py`) computes:

1. **Windowed RMS Magnitude** (whole nominal cycles when available; not phasor estimation):
   $$I_{RMS} = \sqrt{\frac{1}{N} \sum_{k=1}^{N} i[k]^2}$$
   where $N = 80$ samples per cycle at $4000\text{ Hz}$ sampling rate on $50\text{ Hz}$ nominal grid.
2. **Estimated Onset/Pickup-to-Breaker-Contact Interval ($\Delta t$)**:
   $$\Delta t = t_{52a\_open} - t_{pickup}$$
   Uses a 52a falling or 52b rising edge and a detected onset/pickup. No onset means no invented recording-start substitute. Auxiliary-contact opening does not prove electrical fault clearance.
3. **Zero-Crossing Frequency Estimation**:
   $$f = \frac{f_s}{2 \cdot \text{median}(\Delta k_{zero})}$$
4. **Phase Disturbance Attribution**:
   Identifies the faulted phase deterministically by comparing active fault RMS current across all analog channels against nominal load current.

### CT Secondary Note
Compute $I_{sec}=I_{primary}/(CT_{primary}/CT_{secondary})$ only from explicit, positive cited CT metadata. The parser normalizes scaling, units and primary/secondary basis before thresholding and retains that provenance. Never guess a ratio from a fixture-specific constant.
