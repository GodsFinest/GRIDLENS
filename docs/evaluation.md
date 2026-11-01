# Evaluation and ablation contract

## Curated regression

The 26-case suite exercises routing, seeded hypothesis rankings, configuration
conflicts, abstention and supported facts on OGS-01. It is a regression suite,
not a statistically representative field evaluation. Six subsystem ablations
remain available. Their results are computed from the current code, not copied
from historical tables.

The comparator in `services/evaluation/naive_baseline.py` is a **scripted heuristic
negative control, not an LLM**. Its failure rate cannot establish superiority over
a real model. Unconfigured real-provider evaluation returns `not_run`; provider
errors are not silently converted to mock results.

## Physical-input evaluation

Generate 80 development 50 Hz sinusoidal cases and 40 held-out 60 Hz harmonic
cases. Every case creates actual CFG/DAT inputs, passes them through WaveformTool,
the parser/analyzer and the investigation/report workflow, and is scored against
an independent analytic signal oracle. Checks include RMS, phase, pickup,
completeness, onset/contact timing, tool execution and measured report claims.

The waveform families and DAT hashes are disjoint. Both splits still share seeded
topology; this is synthetic signal-family coverage, not held-out topology,
causal diagnosis accuracy or real-world validation. The older latent parameter
JSON files and their historical accuracy tables are not current evidence.

```sh
python -m services.evaluation.physical_cases --split dev
python -m services.evaluation.physical_cases --split heldout
PYTHONPATH=. LLM_PROVIDER=mock MODEL_PROVIDER=mock pytest --cov=domain --cov=services --cov-fail-under=80 -q
```

See [the verification contract](verification.md) for tolerances, test coverage,
input-format limits, and interpretation of the results. Commands emit detailed
per-case output and write generated artifacts under the ignored
`data/evaluation/` directory.

The current pytest collection is 137 tests (96 unit, 17 integration, 17
adversarial, 7 evaluation), derived with
`pytest --collect-only -q | tail -1`. CI and `Makefile` enforce a minimum 80%
coverage gate.

