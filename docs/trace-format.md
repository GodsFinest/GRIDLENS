# Offline execution trace format

**Schema Version**: `1.0.0`
**Compatibility**: LangSmith Run / OpenTelemetry Spans (Offline JSON Format)

---

## 1. Overview

Every investigation run in GridLens executes through a compiled LangGraph workflow.
The `services.agent.trace_exporter` module provides deterministic, offline serialization of complete execution trajectories without requiring external API keys, third-party network egress, or telemetry daemons.

Traces record node transitions, individual tool inputs and outputs, claim verification verdicts, and millisecond-level execution latencies.

---

## 2. Root Run Schema

The top-level JSON object represents the composite workflow run:

| Field | Type | Description |
|---|---|---|
| `id` | `string (UUID)` | Deterministic UUIDv5 generated from investigation ID |
| `name` | `string` | Workflow identifier (`GridLensInvestigationWorkflow:<type>`) |
| `run_type` | `string` | Standard run type descriptor: `"chain"` |
| `investigation_id` | `string` | Primary domain request ID (e.g. `INV-2026-001`) |
| `incident_id` | `string \| null` | Associated incident identifier or null for general QA |
| `investigation_type`| `string` | Domain enum (`PROTECTION_EVENT_INVESTIGATION`, etc.) |
| `start_time` | `string (ISO-8601)`| UTC start timestamp |
| `total_duration_ms`| `float` | Cumulative investigation execution time in ms |
| `inputs` | `object` | Dict containing `user_query`, `incident_id`, `investigation_type` |
| `outputs` | `object` | Final verdicts: `diagnosis_title`, `confidence_score`, `is_sufficient`, `is_faithful`, fact counts |
| `tags` | `array<string>` | Query and categorization tags (`["gridlens", "offline-trace", ...]`) |
| `spans` | `array<Span>` | Chronological list of child node execution spans |
| `metadata` | `object` | Schema version (`1.0.0`), citation counts, export timestamp |

---

## 3. Child Span Schema

Each graph node execution (tool calls, assessment, verifiers) is emitted as a child span:

| Field | Type | Description |
|---|---|---|
| `id` | `string (UUID)` | Deterministic UUIDv5 for the step |
| `parent_run_id` | `string (UUID)` | Root run identifier |
| `name` | `string` | Graph node name (`classify`, `run_waveform`, `verify`, etc.) |
| `run_type` | `string` | `"tool"` (for deterministic domain tools), `"llm"` (synthesis), `"chain"` |
| `tool_name` | `string \| null` | Name of tool invoked (e.g. `WaveformTool`, `TopologyTool`) |
| `inputs` | `object` | Specific parameters passed into the node/tool |
| `outputs` | `object` | Summarized or structured outputs returned |
| `status` | `string` | Node execution status (`SUCCESS`, `SKIPPED`, `ERROR`) |
| `duration_ms` | `float` | Step execution duration in milliseconds |
| `step_index` | `integer` | 1-based sequential ordering index |
| `timestamp` | `string (ISO-8601)`| Execution timestamp |

---

## 4. Programmatic Usage

```python
from services.agent.graph import GridLensInvestigationWorkflow
from services.agent.trace_exporter import export_investigation_trace, save_trace_to_file
from pathlib import Path

workflow = GridLensInvestigationWorkflow()
result = await workflow.run_investigation(request)

# Export as in-memory dictionary:
trace_dict = export_investigation_trace(result)

# Serialize to file:
save_trace_to_file(result, Path("artifacts/traces/run-001.json"))
```
