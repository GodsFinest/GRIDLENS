"""Simulation approval guard preventing any unauthorized simulated grid actions."""
import uuid
from typing import Dict, Any, Optional
from pydantic import BaseModel
from services.safety.rbac import SecurityContext, Permission, UserRole


class SimulatedActionRequest(BaseModel):
    action_id: str
    action_type: str  # e.g., "SIMULATE_BREAKER_CLOSE", "SIMULATE_RELAY_RESET", "SIMULATE_PARAM_UPDATE"
    target_equipment_id: str
    requested_by: str
    justification: str
    status: str = "PENDING_APPROVAL"  # "PENDING_APPROVAL", "APPROVED", "REJECTED", "EXECUTED"
    approver_id: Optional[str] = None
    approval_token: Optional[str] = None


class SimulationGuard:
    """Non-bypassable simulation wall requiring dual-role authorization for simulated operations."""

    def __init__(self):
        self._action_store: Dict[str, SimulatedActionRequest] = {}

    def submit_action_request(
        self,
        security_ctx: SecurityContext,
        action_type: str,
        target_equipment_id: str,
        justification: str,
    ) -> SimulatedActionRequest:
        security_ctx.require_permission(Permission.SUBMIT_SIMULATED_ACTION)

        act_id = f"ACT-{uuid.uuid4().hex[:8].upper()}"
        req = SimulatedActionRequest(
            action_id=act_id,
            action_type=action_type,
            target_equipment_id=target_equipment_id,
            requested_by=security_ctx.username,
            justification=justification,
        )
        self._action_store[act_id] = req
        return req

    def approve_simulated_action(
        self,
        security_ctx: SecurityContext,
        action_id: str,
    ) -> SimulatedActionRequest:
        security_ctx.require_permission(Permission.APPROVE_SIMULATED_ACTION)

        if action_id not in self._action_store:
            raise KeyError(f"Action request '{action_id}' not found.")

        req = self._action_store[action_id]
        if req.requested_by.strip().lower() == security_ctx.username.strip().lower():
            raise PermissionError("Two-person rule violation: Action requester cannot approve their own simulated control action.")

        token = f"APP-TOK-{uuid.uuid4().hex[:12].upper()}"
        req.status = "APPROVED"
        req.approver_id = security_ctx.username
        req.approval_token = token
        return req
