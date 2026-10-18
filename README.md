# GridLens

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688.svg)](https://fastapi.tiangolo.com/)

GridLens analyzes substation protection events from COMTRADE recordings,
sequence-of-events logs, equipment topology, configuration rules, and local
technical references. It produces reports whose measurements and conclusions
remain linked to their source data.

The repository ships with a synthetic OGS-01 dataset and does not connect to
live operational technology.

## Capabilities

- Parse the supported IEEE C37.111 COMTRADE ASCII subset and normalize CT/VT values.
- Calculate RMS values, peaks, event timing, sequence components, and pickup margins.
- Correlate waveform, topology, relay, breaker, and SOE records.
- Detect configuration conflicts and incomplete evidence.
- Track facts, inferences, recommendations, and citations in an evidence ledger.
- Export structured execution traces and expose verification tools over MCP.

## System design

```text
FastAPI / Next.js
        |
LangGraph investigation workflow
        |
COMTRADE | topology | physics | validation | SOE | retrieval | history
        |
evidence ledger -> sufficiency checks -> claim verification -> report
```

Runtime data is stored locally in seeded JSON, COMTRADE, and Markdown files.
The graph and retrieval services use repository interfaces, but no external
database is required. See [architecture.md](docs/architecture.md) for component
boundaries and data flow.

## Run

### Docker Compose

```bash
docker compose up --build
```

- Web console: [http://localhost:3000](http://localhost:3000)
- API documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

### Local development

Python 3.12 and Node.js 22 are recommended.

```bash
make install
.venv/bin/python -m scripts.seed_all
make check
```

Start the services in separate terminals:

```bash
.venv/bin/python apps/api/main.py
```

```bash
cd apps/web
npm run dev
```

Run the MCP server with:

```bash
.venv/bin/python -m services.mcp.server
```

## Configuration

Copy [`.env.example`](.env.example) to `.env` when configuration overrides are
needed. The primary settings are:

| Variable | Purpose |
| --- | --- |
| `GRIDLENS_ENV` | Selects development or production behavior. |
| `GRIDLENS_API_KEYS` | Defines API key, user, and role mappings. |
| `GRIDLENS_ALLOWED_ORIGINS` | Sets allowed browser origins. |
| `LLM_PROVIDER` | Selects deterministic formatting, OpenAI, or Groq. |
| `LLM_MODEL` | Overrides the provider model. |

Production mode requires configured API keys. Keep browser-accessible keys out
of `NEXT_PUBLIC_*` variables; the local console can instead read an explicitly
supplied key from `localStorage.gridlens_api_key`.

## Verification

```bash
make check
.venv/bin/python -m services.evaluation.physical_cases --split dev
.venv/bin/python -m services.evaluation.physical_cases --split heldout
```

`make check` compiles the Python packages, verifies seed integrity, enforces the
coverage threshold, and builds the web application. Evaluation uses synthetic
recordings and seeded topology; it does not measure performance on utility field
data. Detailed limits and tolerances are documented in
[verification.md](docs/verification.md).

## Repository layout

```text
apps/       FastAPI service and Next.js console
data/       COMTRADE, technical references, and seeded topology/incidents
docs/       Architecture, security, format, and evaluation documentation
domain/     Equipment, evidence, claim, hypothesis, and result models
scripts/    Seed generation and integrity checks
services/   Analysis, orchestration, retrieval, safety, and evaluation services
tests/      Unit, integration, adversarial, and evaluation tests
```

Additional references:

- [COMTRADE support](docs/comtrade.md)
- [Evaluation](docs/evaluation.md)
- [Execution trace format](docs/trace-format.md)
- [Security model](docs/security.md)
- [Seeded engineering model](docs/engineering-model.md)
