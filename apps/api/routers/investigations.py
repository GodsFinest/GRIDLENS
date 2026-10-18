"""API routes for running and retrieving investigations."""
import json
import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Depends
from domain.investigation.models import InvestigationRequest, InvestigationResult
from services.agent.graph import GridLensInvestigationWorkflow
from services.safety.api_auth import require_api_key
from services.safety.rbac import SecurityContext, Permission
from services.safety.sanitizer import InputSanitizer
from services.config import INCIDENTS_FILE

router = APIRouter(prefix="/investigations", tags=["Investigations"])

from fastapi.responses import StreamingResponse

# In-memory investigation storage for live review
_INVESTIGATION_CACHE: Dict[str, InvestigationResult] = {}
_INVESTIGATION_EVIDENCE_CACHE: Dict[str, List[Any]] = {}
workflow = GridLensInvestigationWorkflow()
logger = logging.getLogger(__name__)


@router.post("", response_model=InvestigationResult)
async def run_investigation(request: InvestigationRequest, security: SecurityContext = Depends(require_api_key)):
    """Executes a stateful investigation with deterministic tool orchestration and claim verification."""
    try:
        security.require_permission(Permission.RUN_INVESTIGATION)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    # Check for prompt injection attempts
    if InputSanitizer.detect_injection_attempt(request.user_query):
        raise HTTPException(
            status_code=400,
            detail="Potential instruction injection or malicious command detected in user_query.",
        )
    request.user_query = InputSanitizer.sanitize_untrusted_data(request.user_query)

    try:
        # Load incident seed data if incident_id is passed
        incident_data = None
        if request.incident_id:
            with INCIDENTS_FILE.open("r", encoding="utf-8") as f:
                inc_list = json.load(f)
            for inc in inc_list:
                if inc["incident_id"] == request.incident_id.upper():
                    incident_data = inc
                    break

        request.user_role = security.role.value
        result = await workflow.run_investigation(request, incident_data=incident_data)
        _INVESTIGATION_CACHE[result.investigation_id] = result
        _INVESTIGATION_EVIDENCE_CACHE[result.investigation_id] = getattr(result, "_evidence_ledger", [])
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception:
        logger.exception("Investigation execution failed")
        raise HTTPException(status_code=500, detail="Investigation execution failed.")


@router.post("/stream")
async def run_investigation_stream(request: InvestigationRequest, security: SecurityContext = Depends(require_api_key)):
    """SSE streaming endpoint yielding events node-by-node as LangGraph executes."""
    try:
        security.require_permission(Permission.RUN_INVESTIGATION)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if InputSanitizer.detect_injection_attempt(request.user_query):
        raise HTTPException(
            status_code=400,
            detail="Potential instruction injection or malicious command detected in user_query.",
        )
    request.user_query = InputSanitizer.sanitize_untrusted_data(request.user_query)

    incident_data = None
    if request.incident_id:
        with INCIDENTS_FILE.open("r", encoding="utf-8") as f:
            inc_list = json.load(f)
        for inc in inc_list:
            if inc["incident_id"] == request.incident_id.upper():
                incident_data = inc
                break

    request.user_role = security.role.value

    async def event_generator():
        async for event in workflow.stream_investigation(request, incident_data=incident_data):
            if event["event"] == "investigation_completed":
                res = event["result"]
                _INVESTIGATION_CACHE[res.investigation_id] = res
                _INVESTIGATION_EVIDENCE_CACHE[res.investigation_id] = event.get("evidence_ledger", [])
                payload = {
                    "event": "investigation_completed",
                    "result": res.model_dump() if hasattr(res, "model_dump") else res.dict(),
                }
            else:
                payload = event
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{investigation_id}", response_model=InvestigationResult)
async def get_investigation(investigation_id: str, security: SecurityContext = Depends(require_api_key)):
    """Retrieves an existing investigation result."""
    try:
        security.require_permission(Permission.VIEW_INCIDENTS)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if investigation_id in _INVESTIGATION_CACHE:
        return _INVESTIGATION_CACHE[investigation_id]
    raise HTTPException(status_code=404, detail=f"Investigation '{investigation_id}' not found.")


@router.get("/{investigation_id}/provenance")
async def get_investigation_provenance(investigation_id: str, security: SecurityContext = Depends(require_api_key)):
    """Reconstructs the full end-to-end DAG from diagnosis -> claims -> evidence -> tools -> source."""
    try:
        security.require_permission(Permission.VIEW_INCIDENTS)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if investigation_id not in _INVESTIGATION_CACHE:
        raise HTTPException(status_code=404, detail=f"Investigation '{investigation_id}' not found.")

    res = _INVESTIGATION_CACHE[investigation_id]
    ev_list = _INVESTIGATION_EVIDENCE_CACHE.get(investigation_id, [])
    ev_map = {ev.evidence_id: ev for ev in ev_list}

    chains = []
    all_claims = res.verified_facts + res.supported_inferences + res.rejected_claims
    for claim in all_claims:
        ev_items = []
        for eid in claim.evidence_ids:
            if eid in ev_map:
                ev = ev_map[eid]
                ev_items.append({
                    "evidence_id": ev.evidence_id,
                    "kind": ev.kind.value if hasattr(ev.kind, "value") else str(ev.kind),
                    "source_type": ev.source_type.value if hasattr(ev.source_type, "value") else str(ev.source_type),
                    "source_id": ev.source_id,
                    "tool_name": ev.tool_name,
                    "fact": ev.fact,
                    "structured_value": ev.structured_value,
                    "unit": ev.unit,
                    "provenance": ev.provenance,
                    "metadata": ev.metadata,
                })
            else:
                ev_items.append({
                    "evidence_id": eid,
                    "source_id": "UNKNOWN",
                    "fact": f"Evidence reference {eid}",
                })

        chains.append({
            "claim_id": claim.claim_id,
            "claim_statement": claim.statement,
            "claim_type": claim.claim_type.value if hasattr(claim.claim_type, "value") else str(claim.claim_type),
            "status": claim.verification_status.value if hasattr(claim.verification_status, "value") else str(claim.verification_status),
            "verification_notes": claim.verification_notes,
            "evidence_ids": claim.evidence_ids,
            "premise_claim_ids": claim.premise_claim_ids,
            "inference_rule_id": claim.inference_rule_id,
            "evidence_items": ev_items,
        })

    return {
        "investigation_id": res.investigation_id,
        "incident_id": res.incident_id,
        "diagnosis": res.diagnosis_title,
        "diagnosis_summary": res.diagnosis_summary,
        "conflict_lifecycle": res.conflict_lifecycle.value if hasattr(res.conflict_lifecycle, "value") else str(res.conflict_lifecycle),
        "conflict_explanation": res.conflict_explanation,
        "conflict_transitions": [t.model_dump() if hasattr(t, "model_dump") else t.dict() for t in res.conflict_transitions],
        "chains": chains,
    }


@router.get("/{investigation_id}/trace")
async def get_investigation_trace(investigation_id: str, security: SecurityContext = Depends(require_api_key)):
    """Retrieves the full auditable execution trace for an investigation."""
    try:
        security.require_permission(Permission.VIEW_INCIDENTS)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if investigation_id in _INVESTIGATION_CACHE:
        res = _INVESTIGATION_CACHE[investigation_id]
        return {
            "investigation_id": res.investigation_id,
            "investigation_type": res.investigation_type,
            "created_at": res.created_at,
            "duration_ms": res.duration_ms,
            "execution_trace": res.execution_trace,
        }
    raise HTTPException(status_code=404, detail=f"Investigation '{investigation_id}' not found.")
