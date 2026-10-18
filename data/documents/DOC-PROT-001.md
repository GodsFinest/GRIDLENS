# DOC-PROT-001: Power System Protection Fundamentals & ANSI Device Numbers

## Section 1: Overview of Distribution Protection
Power system protection isolates faulted electrical apparatus to minimize equipment damage and maintain grid stability. Protection relays continuously monitor secondary currents and voltages provided by Current Transformers (CTs) and Voltage Transformers (VTs).

## Section 2: ANSI/IEEE Standard Device Function Codes
- **ANSI 50 (Instantaneous Overcurrent Relay)**: Operates with no intentional time delay when the measured AC current exceeds a pre-set high threshold ($I > I_{inst}$). Commonly set above the maximum downstream through-fault level.
- **ANSI 51 (AC Inverse Time Overcurrent Relay)**: Operates with an inverse time characteristic where operating time is inversely proportional to fault current magnitude ($t \propto \frac{1}{(I/I_{pickup})^p - 1}$). Used for coordinated feeder backup and overload protection.
- **ANSI 50N / 51N (Neutral / Ground Overcurrent)**: Detects zero-sequence ground fault current ($3I_0$) resulting from phase-to-ground insulation breakdown.
- **ANSI 27 (Undervoltage)**: Operates when bus or feeder voltage drops below nominal threshold ($V < 0.85 V_n$), indicative of severe close-in faults.
- **ANSI 59 (Overvoltage)**: Operates on sustained overvoltage conditions.
- **ANSI 87 (Differential Protection)**: Compares incoming and outgoing current vectors across a protected zone (e.g. Transformer T1).

## Section 3: Time-Current Characteristic (TCC) Curves
Standard curves (IEEE Very Inverse, Extremely Inverse, IEC Normal Inverse) establish coordination between upstream transformer breakers and downstream feeder breakers. The time dial multiplier ($TD$) scales the curve vertically.

## Section 4: Fault Clearing Sequence
1. Disturbance inception at $t=0$.
2. Secondary current exceeds relay pickup threshold ($I_{meas} > I_{pkp}$) at $t \approx 10-15\text{ ms}$.
3. Relay logic issues trip command to breaker trip coil at $t \approx 20\text{ ms}$.
4. Circuit breaker main contacts separate and extinguish the electrical arc at $t \approx 50-70\text{ ms}$.
5. Line current collapses to zero.
