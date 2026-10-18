"""API router for physics-constrained generative helpers.

All numbers come from deterministic calculators; the LLM layer
must quote `narrative_numbers` / verdict fields verbatim.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Tuple

from services.physics.symmetrical import classify_from_rms, classify_from_measurements
from services.physics.counterfactual import CounterfactualInput, simulate
from services.physics.settings_advisor import SettingProposal, evaluate
from services.safety.api_auth import require_api_key
from services.safety.rbac import SecurityContext, Permission

router = APIRouter(prefix="/physics", tags=["Physics-Constrained GenAI"])


class RMSInput(BaseModel):
    ia_rms: float
    ib_rms: float
    ic_rms: float


class PhasorInput(BaseModel):
    measurements: Dict[str, Tuple[float, float]]


class CounterfactualRequest(CounterfactualInput):
    pass


class SettingRequest(BaseModel):
    proposal: SettingProposal
    max_load_a: float
    min_fault_a: float


@router.post("/symmetrical/rms")
async def symmetrical_rms(req: RMSInput, security: SecurityContext = Depends(require_api_key)):
    try:
        security.require_permission(Permission.VIEW_INCIDENTS)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return classify_from_rms(req.ia_rms, req.ib_rms, req.ic_rms)


@router.post("/symmetrical/phasor")
async def symmetrical_phasor(req: PhasorInput, security: SecurityContext = Depends(require_api_key)):
    try:
        security.require_permission(Permission.VIEW_INCIDENTS)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return classify_from_measurements(req.measurements)


@router.post("/counterfactual/simulate")
async def counterfactual_simulate(req: CounterfactualRequest, security: SecurityContext = Depends(require_api_key)):
    try:
        security.require_permission(Permission.VIEW_INCIDENTS)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return simulate(req)


@router.post("/settings/evaluate")
async def settings_evaluate(req: SettingRequest, security: SecurityContext = Depends(require_api_key)):
    try:
        security.require_permission(Permission.VIEW_INCIDENTS)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return evaluate(req.proposal, req.max_load_a, req.min_fault_a)
