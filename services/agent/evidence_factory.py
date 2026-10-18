"""EvidenceFactory converting typed tool output results into atomic Evidence objects."""
from typing import List
import re
from domain.evidence.models import Evidence, EvidenceSourceType, EvidenceKind
from domain.models.results import (
    TopologyQueryResult,
    ComtradeAnalysisResult,
    ValidationResult,
    EventTimelineResult,
    DocumentRetrievalResult,
    HistoricalIncidentResult,
)
from services.tools.physics_tool import PhysicsAnalysisResult

class EvidenceFactory:
    """Deterministic factory producing atomic, provenance-tracked Evidence objects."""

    @classmethod
    def from_topology(cls, topo: TopologyQueryResult) -> List[Evidence]:
        evidence_list: List[Evidence] = []
        if not topo.is_topology_complete:
            evidence_list.append(Evidence(
                evidence_id="EV_TOPO_MISSING",
                kind=EvidenceKind.TOPO_MISSING,
                source_type=EvidenceSourceType.GRAPH,
                source_id="IN_MEMORY_TOPOLOGY",
                tool_name="TopologyTool",
                fact=f"Feeder {topo.feeder_id} topology records are incomplete or missing.",
                structured_value=False,
                provenance="DirectedGraph traversal",
                deterministic=True,
            ))
            return evidence_list

        evidence_list.append(Evidence(
            evidence_id="EV_TOPO_PRIMARY_RELAY",
            kind=EvidenceKind.TOPO_PRIMARY_RELAY,
            source_type=EvidenceSourceType.GRAPH,
            source_id="IN_MEMORY_TOPOLOGY",
            tool_name="TopologyTool",
            fact=f"{topo.primary_relay_id} is configured as the primary protection relay for Feeder {topo.feeder_id}.",
            structured_value=topo.primary_relay_id,
            provenance=f"Substation OGS-01 -> Bay {topo.bay_id} -> {topo.feeder_id}",
            deterministic=True,
        ))

        evidence_list.append(Evidence(
            evidence_id="EV_TOPO_BREAKER",
            kind=EvidenceKind.TOPO_BREAKER,
            source_type=EvidenceSourceType.GRAPH,
            source_id="IN_MEMORY_TOPOLOGY",
            tool_name="TopologyTool",
            fact=f"Feeder {topo.feeder_id} is controlled by circuit breaker {topo.controlled_breaker_id} on {topo.connected_bus_id}.",
            structured_value=topo.controlled_breaker_id,
            provenance=f"Bay {topo.bay_id} breaker association",
            deterministic=True,
        ))

        evidence_list.append(Evidence(
            evidence_id="EV_TOPO_SENSORS",
            kind=EvidenceKind.TOPO_SENSORS,
            source_type=EvidenceSourceType.GRAPH,
            source_id="IN_MEMORY_TOPOLOGY",
            tool_name="TopologyTool",
            fact=f"Feeder {topo.feeder_id} is monitored by instrument sensors {', '.join(topo.sensor_ids)} feeding {topo.ied_id}.",
            structured_value=topo.sensor_ids,
            provenance="Sensor-to-IED CT/VT wiring table",
            deterministic=True,
        ))
        return evidence_list

    @classmethod
    def from_comtrade(cls, comtrade: ComtradeAnalysisResult) -> List[Evidence]:
        evidence_list: List[Evidence] = []
        if comtrade.is_truncated:
            evidence_list.append(Evidence(
                evidence_id="EV_COMTRADE_TRUNCATED",
                kind=EvidenceKind.RECORDING_TRUNCATED,
                source_type=EvidenceSourceType.COMTRADE,
                source_id=f"{comtrade.incident_id}.CFG",
                tool_name="WaveformTool",
                fact=("COMTRADE recording is incomplete: DAT contains fewer samples than declared in CFG." if comtrade.total_samples
                      else "COMTRADE analysis is unavailable or invalid; no physical measurements were established."),
                structured_value=True,
                provenance="COMTRADE header sample count check",
                deterministic=True,
            ))

        for ch_name, m in comtrade.analog_measurements.items():
            ev_id = f"EV_COMTRADE_RMS_{ch_name}"
            evidence_list.append(Evidence(
                evidence_id=ev_id,
                kind=EvidenceKind.CHANNEL_RMS,
                source_type=EvidenceSourceType.COMTRADE,
                source_id=f"{comtrade.incident_id}.DAT",
                tool_name="WaveformTool",
                fact=f"Channel {ch_name} measured Pre-fault RMS: {m.pre_fault_rms} {m.unit}, Fault RMS: {m.fault_rms} {m.unit} (Peak: {m.peak_value} {m.unit}).",
                structured_value=m.fault_rms,
                unit=m.unit,
                provenance=f"Sliding-window RMS calculation on channel {ch_name}",
                deterministic=True,
                metadata={"channel": ch_name, "phase": m.phase, "pre_fault_rms": m.pre_fault_rms,
                          "fault_rms": m.fault_rms, "peak_value": m.peak_value, "normalization": m.normalization,
                          "ct_ratio": (m.normalization["primary_ratio"] / m.normalization["secondary_ratio"]
                                       if m.normalization.get("secondary_ratio", 0) > 0 else None)},
            ))

        if comtrade.pickup_exceeded and comtrade.fault_phase_detected:
            evidence_list.append(Evidence(
                evidence_id="EV_COMTRADE_OVERCURRENT_EXCEEDED",
                kind=EvidenceKind.OVERCURRENT_EXCEEDED,
                source_type=EvidenceSourceType.COMTRADE,
                source_id=f"{comtrade.incident_id}.DAT",
                tool_name="WaveformTool",
                fact=f"Overcurrent threshold ({comtrade.pickup_threshold_a} A) was exceeded on {comtrade.fault_phase_detected}.",
                structured_value=True,
                unit="A",
                provenance="Current threshold comparison",
                deterministic=True,
                metadata={"fault_phase": comtrade.fault_phase_detected, "pickup_threshold_a": comtrade.pickup_threshold_a},
            ))

        if comtrade.total_clearing_time_ms is not None:
            evidence_list.append(Evidence(
                evidence_id="EV_COMTRADE_CLEARING_TIME",
                kind=EvidenceKind.CLEARING_TIME,
                source_type=EvidenceSourceType.COMTRADE,
                source_id=f"{comtrade.incident_id}.DAT",
                tool_name="WaveformTool",
                fact=f"Estimated disturbance-onset/pickup-to-breaker-contact interval was {comtrade.total_clearing_time_ms} ms; contact indication alone does not prove electrical clearance.",
                structured_value=comtrade.total_clearing_time_ms,
                unit="ms",
                provenance="Delta t from estimated waveform onset (or pickup edge) to breaker contact indication",
                metadata={"onset_time_ms": comtrade.onset_time_ms, "pickup_time_ms": comtrade.pickup_time_ms,
                          "breaker_open_time_ms": comtrade.breaker_open_time_ms},
                deterministic=True,
            ))
        return evidence_list

    @classmethod
    def from_validation(cls, val: ValidationResult) -> List[Evidence]:
        evidence_list: List[Evidence] = []
        if val.valid:
            evidence_list.append(Evidence(
                evidence_id="EV_VALIDATION_PASSED",
                kind=EvidenceKind.CONFIG_PASSED,
                source_type=EvidenceSourceType.CONFIG_VALIDATOR,
                source_id="CONFIG_VALIDATOR",
                tool_name="ValidationTool",
                fact="Substation engineering configuration and channel mapping rules passed with 0 violations.",
                structured_value=True,
                provenance="Deterministic ValidationRuleEngine",
                deterministic=True,
            ))
        else:
            for index, v in enumerate(val.violations, start=1):
                kind = EvidenceKind.PHASE_INVERSION_VIOLATION if v.rule_id == "RULE-MAP-003" else EvidenceKind.CONFIG_VIOLATION
                evidence_list.append(Evidence(
                    evidence_id=f"EV_VALIDATION_VIOLATION_{v.rule_id}_{index}",
                    kind=kind,
                    source_type=EvidenceSourceType.CONFIG_VALIDATOR,
                    source_id="CONFIG_VALIDATOR",
                    tool_name="ValidationTool",
                    fact=f"Configuration rule violation [{v.rule_id}]: {v.message}",
                    structured_value=v.rule_id,
                    provenance=f"Rule check {v.rule_name} on {v.entity_id}",
                    deterministic=True,
                    metadata={"rule_id": v.rule_id, "rule_name": v.rule_name, "remediation": v.remediation_advice},
                ))
        return evidence_list

    @classmethod
    def from_timeline(cls, tl: EventTimelineResult) -> List[Evidence]:
        evidence_list: List[Evidence] = []
        for ev in tl.ordered_events:
            ev_id = f"EV_SOE_{ev['event_id']}"
            evidence_list.append(Evidence(
                evidence_id=ev_id,
                kind=EvidenceKind.SOE_EVENT,
                source_type=EvidenceSourceType.EVENT_LOG,
                source_id=tl.incident_id,
                tool_name="SOETool",
                fact=f"At {ev['timestamp']} ({ev['offset_ms']} ms): {ev['source_device']} recorded {ev['event_type']} - {ev['description']}",
                structured_value=ev['event_type'],
                timestamp=ev['timestamp'],
                provenance=f"{ev['source_device']} SOE buffer",
                deterministic=True,
                metadata={
                    "event_type": ev.get("event_type"),
                    "channel_or_function": ev.get("channel_or_function"),
                    "value": ev.get("value"),
                    "offset_ms": ev.get("offset_ms"),
                    "disturbance_offset_ms": ev.get("disturbance_offset_ms"),
                },
            ))
        return evidence_list

    @classmethod
    def from_documents(cls, docs: DocumentRetrievalResult) -> List[Evidence]:
        evidence_list: List[Evidence] = []
        for ch in docs.chunks:
            evidence_list.append(Evidence(
                evidence_id=f"EV_DOC_{ch.chunk_id}",
                kind=EvidenceKind.DOC_CHUNK,
                source_type=EvidenceSourceType.DOCUMENT,
                source_id=ch.doc_id,
                tool_name="RetrievalTool",
                fact=next((sentence for sentence in re.split(r'(?<=[.!?])\s+|\n+', ch.content.strip())
                           if len(sentence) > 30), ch.content.strip()),
                structured_value=ch.chunk_id,
                provenance=f"{ch.doc_id} -> {ch.section}",
                deterministic=False,
                metadata={"title": ch.title, "full_content": ch.content, "score": ch.score},
            ))
        return evidence_list

    @classmethod
    def from_history(cls, hist: HistoricalIncidentResult) -> List[Evidence]:
        evidence_list: List[Evidence] = []
        for inc in hist.matching_incidents:
            evidence_list.append(Evidence(
                evidence_id=f"EV_HIST_{inc.incident_id}",
                kind=EvidenceKind.HIST_RECORD,
                source_type=EvidenceSourceType.INCIDENT_HISTORY,
                source_id=inc.incident_id,
                tool_name="HistoryTool",
                fact=f"Past Incident {inc.incident_id} ({inc.timestamp[:10]}): Feeder {inc.feeder_id} tripped on '{inc.fault_type}'. Root cause: {inc.root_cause}",
                structured_value=inc.root_cause,
                provenance="Historical Substation Fault Database",
                deterministic=True,
            ))
        return evidence_list

    @classmethod
    def from_physics(cls, phys: PhysicsAnalysisResult) -> List[Evidence]:
        """Symmetrical-components + setting-check facts from measured waveform data.

        Produces no evidence when the tool skipped (truncated recording or
        missing phases) — the pipeline fails closed instead of guessing.
        """
        evidence_list: List[Evidence] = []
        if phys.classification is None:
            return evidence_list

        c = phys.classification
        if c.sequence_trusted:
            seq_note = f"I0={c.i0_mag}A I1={c.i1_mag}A I2={c.i2_mag}A from true phasors."
        else:
            seq_note = "Sequence magnitudes unavailable from RMS magnitudes alone; phasor angles required."
        evidence_list.append(Evidence(
            evidence_id=f"EV_PHYSICS_CLASS_{phys.incident_id}",
            kind=EvidenceKind.FAULT_CLASSIFICATION,
            source_type=EvidenceSourceType.COMTRADE,
            source_id=f"{phys.incident_id}.DAT",
            tool_name="PhysicsTool",
            fact=f"Symmetrical-components analysis ({c.basis}) classified {c.fault_type} on phase(s) {c.faulted_phase}. {seq_note}",
            structured_value=c.fault_type,
            provenance="Fortescue decomposition of measured phase-current RMS/phasors",
            deterministic=True,
            metadata={
                "fault_type": c.fault_type, "faulted_phase": c.faulted_phase,
                "i0_mag": c.i0_mag, "i1_mag": c.i1_mag, "i2_mag": c.i2_mag,
                "basis": c.basis, "sequence_trusted": c.sequence_trusted,
            },
        ))

        if phys.setting_verdict is not None:
            v = phys.setting_verdict
            status = "VALID" if v.valid else "INVALID"
            evidence_list.append(Evidence(
                evidence_id=f"EV_PHYSICS_SETTING_{phys.incident_id}",
                kind=EvidenceKind.SETTING_VERDICT,
                source_type=EvidenceSourceType.CONFIG_VALIDATOR,
                source_id="CONFIG_VALIDATOR",
                tool_name="PhysicsTool",
                fact=f"Pickup setting check: {v.pickup_a}A with sensitivity {v.sensitivity} and load margin {v.load_margin} is {status} for measured fault current.",
                structured_value=v.valid,
                provenance="Pickup vs measured fault current and feeder continuous rating",
                deterministic=True,
                metadata={"pickup_a": v.pickup_a, "sensitivity": v.sensitivity,
                          "load_margin": v.load_margin, "violations": v.violations},
            ))
        return evidence_list
