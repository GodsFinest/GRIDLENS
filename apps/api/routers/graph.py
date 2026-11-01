"""API router for Substation Knowledge Graph and topology querying."""
from fastapi import APIRouter, HTTPException, Depends
from services.graph.repository import InMemoryGraphRepository
from services.safety.api_auth import require_api_key
from services.safety.rbac import SecurityContext, Permission

router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])
graph_repo = InMemoryGraphRepository()


@router.get("/topology")
async def get_substation_topology(security: SecurityContext = Depends(require_api_key)):
    """Retrieves full Single-Line Diagram topology and equipment hierarchy for Substation OGS-01."""
    try:
        security.require_permission(Permission.VIEW_INCIDENTS)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return await graph_repo.get_substation_topology()


@router.get("/feeder/{feeder_id}/protection-chain")
async def get_feeder_protection_chain(feeder_id: str, security: SecurityContext = Depends(require_api_key)):
    """Retrieves upstream bus, primary relay, breaker, sensors, and downstream loads for a feeder."""
    try:
        security.require_permission(Permission.VIEW_INCIDENTS)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return await graph_repo.get_feeder_protection_chain(feeder_id)


@router.get("/equipment/{equipment_id}")
async def get_equipment_details(equipment_id: str, security: SecurityContext = Depends(require_api_key)):
    """Retrieves detailed relationships and parameters for any substation equipment."""
    try:
        security.require_permission(Permission.VIEW_INCIDENTS)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    res = await graph_repo.get_equipment_relationships(equipment_id)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res
