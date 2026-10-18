"""Domain models for physical and logical power system equipment in Orion Grid Substation OGS-01."""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class EquipmentType(str, Enum):
    SUBSTATION = "SUBSTATION"
    BUS = "BUS"
    FEEDER = "FEEDER"
    TRANSFORMER = "TRANSFORMER"
    BREAKER = "BREAKER"
    IED = "IED"
    RELAY = "RELAY"
    LOGICAL_NODE = "LOGICAL_NODE"
    SENSOR = "SENSOR"
    MEASUREMENT = "MEASUREMENT"


class SensorType(str, Enum):
    CURRENT_TRANSFORMER = "CURRENT_TRANSFORMER"  # CT
    VOLTAGE_TRANSFORMER = "VOLTAGE_TRANSFORMER"  # VT


class Phase(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    NEUTRAL = "N"
    THREE_PHASE = "3P"


class BreakerState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    TRIPPED = "TRIPPED"
    UNKNOWN = "UNKNOWN"


class ProtectionFunctionCode(str, Enum):
    ANSI_50 = "50"    # Instantaneous Overcurrent
    ANSI_51 = "51"    # Time Overcurrent
    ANSI_50N = "50N"  # Neutral Instantaneous Overcurrent
    ANSI_51N = "51N"  # Neutral Time Overcurrent
    ANSI_27 = "27"    # Undervoltage
    ANSI_59 = "59"    # Overvoltage
    ANSI_87 = "87"    # Differential


class Sensor(BaseModel):
    sensor_id: str
    name: str
    sensor_type: SensorType
    phase: Phase
    primary_rating: float
    secondary_rating: float
    ratio: float
    accuracy_class: str = "0.2S"
    bay_id: str


class LogicalNode(BaseModel):
    ln_id: str
    ln_class: str  # e.g., "PIOC", "PTOC", "MMXU", "XCBR", "CSWI", "TCTR", "TVTR"
    instance: int = 1
    description: str
    protection_function: Optional[ProtectionFunctionCode] = None
    settings: Dict[str, Any] = Field(default_factory=dict)


class IED(BaseModel):
    ied_id: str
    name: str
    model: str = "SIPROTEC 5 - 7SJ85"
    ip_address: str
    bay_id: str
    logical_nodes: List[LogicalNode] = Field(default_factory=list)
    ct_channel_mapping: Dict[str, str] = Field(default_factory=dict)  # Commissioned design e.g. {"CH1": "CT12A", "CH2": "CT12B", "CH3": "CT12C"}
    vt_channel_mapping: Dict[str, str] = Field(default_factory=dict)
    declared_channel_phase_map: Optional[Dict[str, str]] = None  # As-found / declared configuration e.g. {"CH1": "CT12C", "CH2": "CT12B", "CH3": "CT12A"}


class Relay(BaseModel):
    relay_id: str
    name: str
    ied_id: str
    bay_id: str
    protected_feeder_id: str
    controlled_breaker_id: str
    active_functions: List[ProtectionFunctionCode] = Field(default_factory=list)
    pickup_current_a: float = 2500.0
    time_dial: float = 0.1
    curve_type: str = "IEEE_VERY_INVERSE"
    declared_channel_phase_map: Optional[Dict[str, str]] = None


class Breaker(BaseModel):
    breaker_id: str
    name: str
    bay_id: str
    rated_voltage_kv: float = 11.0
    rated_current_a: float = 2000.0
    breaking_capacity_ka: float = 25.0
    state: BreakerState = BreakerState.CLOSED
    close_time_ms: float = 65.0
    open_time_ms: float = 35.0


class Feeder(BaseModel):
    feeder_id: str
    name: str
    voltage_level_kv: float = 11.0
    rated_continuous_load_a: float = 630.0
    connected_bus_id: str
    breaker_id: str
    primary_relay_id: str
    length_km: float = 8.5
    feeder_type: str = "INDUSTRIAL_UNDERGROUND"


class Transformer(BaseModel):
    transformer_id: str
    name: str
    primary_voltage_kv: float = 33.0
    secondary_voltage_kv: float = 11.0
    rated_mva: float = 25.0
    vector_group: str = "Dyn11"
    impedance_percent: float = 8.5


class Bus(BaseModel):
    bus_id: str
    name: str
    nominal_voltage_kv: float = 11.0
    connected_feeders: List[str] = Field(default_factory=list)
    connected_transformers: List[str] = Field(default_factory=list)


class Substation(BaseModel):
    substation_id: str = "OGS-01"
    name: str = "Orion Grid Substation OGS-01"
    grid_region: str = "Northern Distribution Zone"
    voltage_levels: List[float] = [33.0, 11.0]
    buses: List[Bus] = Field(default_factory=list)
    feeders: List[Feeder] = Field(default_factory=list)
    transformers: List[Transformer] = Field(default_factory=list)
    breakers: List[Breaker] = Field(default_factory=list)
    relays: List[Relay] = Field(default_factory=list)
    ieds: List[IED] = Field(default_factory=list)
    sensors: List[Sensor] = Field(default_factory=list)
