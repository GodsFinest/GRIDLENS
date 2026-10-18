"""API router for simulated action request submission and dual-role approval gateway."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from services.safety.rbac import SecurityContext, UserRole
from services.safety.simulation_guard import SimulationGuard, SimulatedActionRequest
from services.safety.api_auth import require_api_key

from services.safety.sanitizer import InputSanitizer

router = APIRouter(prefix="/actions", tags=["Simulated Actions"])
guard = SimulationGuard()


class SubmitSimulatedActionRequest(BaseModel):
    action_type: str  # e.g., "SIMULATE_BREAKER_CLOSE", "SIMULATE_RELAY_RESET"
    target_equipment_id: str  # e.g., "CB12"
    requested_by: str = "engineer_alice"
    user_role: str = "ENGINEER"
    justification: str = "Pre-reclosure simulation test following line inspection."


class ApproveSimulatedActionRequest(BaseModel):
    approver_username: str = "supervisor_bob"
    approver_role: str = "APPROVER"


@router.post("/simulate", response_model=SimulatedActionRequest)
async def submit_simulated_action(request: SubmitSimulatedActionRequest, security: SecurityContext = Depends(require_api_key)):
    """Submits a simulated engineering action request into the approval queue."""
    if InputSanitizer.detect_injection_attempt(request.justification):
        raise HTTPException(status_code=400, detail="Potential instruction injection detected in justification.")
    request.justification = InputSanitizer.sanitize_untrusted_data(request.justification)

    try:
        role = security.role
    except ValueError:
        role = UserRole.ENGINEER

    ctx = security
    try:
        req = guard.submit_action_request(
            security_ctx=ctx,
            action_type=request.action_type,
            target_equipment_id=request.target_equipment_id,
            justification=request.justification,
        )
        return req
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


@router.post("/{action_id}/approve", response_model=SimulatedActionRequest)
async def approve_simulated_action(action_id: str, request: ApproveSimulatedActionRequest, security: SecurityContext = Depends(require_api_key)):
    """Approves a simulated action with opaque approval reference issuance (no execution endpoint consumes the token; simulation only) (two-person rule)."""
    try:
        role = security.role
    except ValueError:
        role = UserRole.APPROVER

    ctx = security
    try:
        req = guard.approve_simulated_action(security_ctx=ctx, action_id=action_id)
        return req
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found.")
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
