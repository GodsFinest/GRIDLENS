"""Domain models for substation protection incidents, event logs, and sequence of events."""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class IncidentSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, Enum):
    NEW = "NEW"
    INVESTIGATING = "INVESTIGATING"
    DIAGNOSED = "DIAGNOSED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CLOSED = "CLOSED"


class SOEEvent(BaseModel):
    event_id: str
    timestamp: str  # ISO-8601 or millisecond precision string e.g. "14:32:17.014"
    offset_ms: float
    source_device: str  # e.g. "RELAY-12", "CB12", "IED-12", "SCADA"
    event_type: str  # e.g. "PICKUP", "TRIP_COMMAND", "BREAKER_OPEN", "DISTURBANCE_START", "CURRENT_COLLAPSE"
    channel_or_function: str  # e.g. "ANSI_51P", "52A_CONTACT", "PHASE_C"
    description: str
    value: Optional[Any] = None


class Incident(BaseModel):
    incident_id: str
    title: str
    substation_id: str = "OGS-01"
    feeder_id: str
    bay_id: str
    timestamp: str
    severity: IncidentSeverity = IncidentSeverity.HIGH
    status: IncidentStatus = IncidentStatus.NEW
    apparent_cause_text: str  # Initial unverified operator/alarm text
    comtrade_file_id: Optional[str] = None
    involved_breaker_id: str
    involved_relay_id: str
    involved_ied_id: str
    declared_channel_phase_map: Optional[Dict[str, str]] = None
    events: List[SOEEvent] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
