"""API router for incident catalog, event logs, and COMTRADE waveform oscillography."""
import json
import os
import re
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from domain.models.incident import Incident
from services.comtrade.parser import ComtradeParser
from services.comtrade.analyzer import ComtradeSignalAnalyzer
from services.config import COMTRADE_DIR, INCIDENTS_FILE
from services.safety.api_auth import require_api_key
from services.safety.rbac import SecurityContext, Permission

router = APIRouter(prefix="/incidents", tags=["Incidents"])


@router.get("", response_model=List[Incident])
async def list_incidents(security: SecurityContext = Depends(require_api_key)):
    """Lists all active and historical incidents in Orion Grid Substation OGS-01."""
    try:
        security.require_permission(Permission.VIEW_INCIDENTS)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    with INCIDENTS_FILE.open("r", encoding="utf-8") as f:
        incidents = json.load(f)
    return incidents


@router.get("/{incident_id}", response_model=Incident)
async def get_incident(incident_id: str, security: SecurityContext = Depends(require_api_key)):
    """Retrieves metadata and sequence-of-events logs for a specific incident."""
    try:
        security.require_permission(Permission.VIEW_INCIDENTS)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    with INCIDENTS_FILE.open("r", encoding="utf-8") as f:
        incidents = json.load(f)
    for inc in incidents:
        if inc["incident_id"] == incident_id.upper():
            return inc
    raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")


@router.get("/{incident_id}/comtrade")
async def get_incident_comtrade(incident_id: str, security: SecurityContext = Depends(require_api_key)):
    """Parses COMTRADE oscillography and returns structured time-series and signal measurements."""
    try:
        security.require_permission(Permission.VIEW_INCIDENTS)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    inc_upper = incident_id.upper()
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9\-_]*', inc_upper):
        raise HTTPException(status_code=400, detail=f"Invalid incident identifier '{incident_id}'.")
    cfg_path = os.path.join(str(COMTRADE_DIR), f"{inc_upper}.CFG")
    dat_path = os.path.join(str(COMTRADE_DIR), f"{inc_upper}.DAT")

    if not os.path.exists(cfg_path) or not os.path.exists(dat_path):
        raise HTTPException(status_code=404, detail=f"COMTRADE records for incident '{incident_id}' not found.")

    record = ComtradeParser.parse_files(cfg_path, dat_path)
    analysis = ComtradeSignalAnalyzer.analyze_record(record=record, incident_id=inc_upper)

    # Downsample time-series for frontend chart visualization (keep every 2nd or 4th sample if high rate)
    step = 2 if len(record.sample_indices) > 500 else 1
    sampled_indices = list(range(0, len(record.sample_indices), step))

    time_series = []
    for idx in sampled_indices:
        point = {
            "time_ms": round(record.time_milliseconds[idx], 2),
            "sample_index": record.sample_indices[idx],
        }
        for ch_name, values in record.analog_data.items():
            point[ch_name] = round(values[idx], 2)
        for d_name, bits in record.digital_data.items():
            point[d_name] = bits[idx]
        time_series.append(point)

    return {
        "incident_id": inc_upper,
        "station_name": record.header.station_name,
        "device_name": record.header.device_name,
        "sample_rate_hz": record.header.sampling_rates[0][0] if record.header.sampling_rates else 4000.0,
        "total_samples": len(record.sample_indices),
        "duration_ms": record.time_milliseconds[-1] - record.time_milliseconds[0] if len(record.time_milliseconds) > 1 else 0.0,
        "is_truncated": record.is_truncated,
        "analog_channels": [ch.model_dump() if hasattr(ch, "model_dump") else ch.dict() for ch in record.header.analog_channels],
        "digital_channels": [d.model_dump() if hasattr(d, "model_dump") else d.dict() for d in record.header.digital_channels],
        "measurements": analysis.model_dump() if hasattr(analysis, "model_dump") else analysis.dict(),
        "time_series": time_series,
    }
