"""Typed tool output results providing deterministic contracts between tool execution and the evidence pipeline."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TopologyQueryResult(BaseModel):
    feeder_id: str
    bay_id: str
    connected_bus_id: str
    primary_relay_id: str
    controlled_breaker_id: str
    ied_id: str
    sensor_ids: List[str] = Field(default_factory=list)
    upstream_transformer_id: Optional[str] = None
    downstream_equipment: List[str] = Field(default_factory=list)
    is_topology_complete: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChannelMeasurement(BaseModel):
    channel_name: str
    phase: str
    pre_fault_rms: float
    fault_rms: float
    peak_value: float
    delta_value: float
    unit: str
    normalization: Dict[str, Any] = Field(default_factory=dict)


class ComtradeAnalysisResult(BaseModel):
    incident_id: str
    sample_rate_hz: float
    total_samples: int
    duration_ms: float
    is_truncated: bool = False
    analog_measurements: Dict[str, ChannelMeasurement] = Field(default_factory=dict)
    frequency_hz: Optional[float] = None
    fault_phase_detected: Optional[str] = None
    pickup_threshold_a: Optional[float] = None
    pickup_exceeded: bool = False
    onset_time_ms: Optional[float] = None
    pre_fault_window_ms: Optional[List[float]] = None
    pickup_time_ms: Optional[float] = None
    trip_time_ms: Optional[float] = None
    breaker_open_time_ms: Optional[float] = None
    total_clearing_time_ms: Optional[float] = None
    digital_transitions: List[Dict[str, Any]] = Field(default_factory=list)
    analysis_notes: List[str] = Field(default_factory=list)


class ValidationViolation(BaseModel):
    rule_id: str
    rule_name: str
    entity_id: str
    entity_type: str
    severity: str = "ERROR"  # "ERROR", "WARNING", "INFO"
    message: str
    remediation_advice: str


class ValidationResult(BaseModel):
    target_entity_id: str
    valid: bool
    violations: List[ValidationViolation] = Field(default_factory=list)
    checks_performed: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EventTimelineResult(BaseModel):
    incident_id: str
    ordered_events: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp_precision: str = "1ms"
    synchronization_status: str = "SYNCHRONIZED"  # "SYNCHRONIZED", "UNSYNCHRONIZED", "DESYNCHRONIZED_ANOMALY"
    total_duration_ms: Optional[float] = None
    anomalies: List[str] = Field(default_factory=list)


class RetrievedDocumentChunk(BaseModel):
    doc_id: str
    title: str
    section: str
    chunk_id: str
    content: str
    score: float
    relevance_reason: Optional[str] = None


class DocumentRetrievalResult(BaseModel):
    query: str
    retrieval_method: str = "HYBRID_BM25_VECTOR_RRF"
    chunks: List[RetrievedDocumentChunk] = Field(default_factory=list)
    total_chunks_found: int = 0


class HistoricalIncidentSummary(BaseModel):
    incident_id: str
    timestamp: str
    feeder_id: str
    fault_type: str
    root_cause: str
    clearing_time_ms: float
    similarity_factors: List[str] = Field(default_factory=list)


class HistoricalIncidentResult(BaseModel):
    query_feeder_id: str
    matching_incidents: List[HistoricalIncidentSummary] = Field(default_factory=list)
