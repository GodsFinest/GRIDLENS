"""API router for deterministic substation configuration validation."""
from typing import Optional, Dict
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from domain.models.results import ValidationResult
from services.validation.validator import ConfigurationValidator
from services.graph.repository import InMemoryGraphRepository
from services.safety.api_auth import require_api_key
from services.safety.rbac import SecurityContext, Permission

router = APIRouter(prefix="/validation", tags=["Configuration Validation"])
validator = ConfigurationValidator(InMemoryGraphRepository())


class ValidationRunRequest(BaseModel):
    bay_id: str = "BAY_F12"
    feeder_id: Optional[str] = "F12"
    ied_id: Optional[str] = "IED_12"
    custom_ct_mapping: Optional[Dict[str, str]] = None


@router.post("/run", response_model=ValidationResult)
async def run_configuration_validation(request: ValidationRunRequest, security: SecurityContext = Depends(require_api_key)):
    """Executes deterministic engineering rule validation against bay parameters and channel mappings."""
    try:
        security.require_permission(Permission.RUN_VALIDATION)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    try:
        result = await validator.validate_bay_configuration(
            bay_id=request.bay_id,
            feeder_id=request.feeder_id,
            ied_id=request.ied_id,
            custom_ied_mapping=request.custom_ct_mapping,
        )
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
