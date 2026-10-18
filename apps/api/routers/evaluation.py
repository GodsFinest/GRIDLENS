"""API router for benchmark evaluation suite and ablation comparison."""
import time
from fastapi import APIRouter, Depends, HTTPException
from services.evaluation.evaluator import SystemEvaluator
from services.safety.api_auth import require_api_key
from services.safety.rbac import SecurityContext, Permission

router = APIRouter(prefix="/evaluation", tags=["Evaluation & Benchmarks"])

# Cache comparative benchmark results to avoid re-running ~208 investigations per page load.
# get_comparative_benchmark() executes Full GridLens + 6 ablations + baseline (≈208
# workflow runs); cache the payload for 1h so dashboard polling stays cheap.
_EVAL_CACHE: dict = {"payload": None, "timestamp": 0.0}
_EVAL_CACHE_TTL_SECONDS = 3600.0


@router.get("/results")
async def get_evaluation_results(security: SecurityContext = Depends(require_api_key)):
    """Retrieves comparative benchmark results between Baseline, Full GridLens, and 6 Ablations."""
    try:
        security.require_permission(Permission.VIEW_INCIDENTS)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    now = time.time()
    cached_payload = _EVAL_CACHE.get("payload")
    cached_ts = _EVAL_CACHE.get("timestamp", 0.0)
    if cached_payload is not None and (now - cached_ts) < _EVAL_CACHE_TTL_SECONDS:
        return cached_payload
    result = await SystemEvaluator.get_comparative_benchmark()
    _EVAL_CACHE["payload"] = result
    _EVAL_CACHE["timestamp"] = now
    return result


@router.post("/run")
async def trigger_evaluation_run(security: SecurityContext = Depends(require_api_key)):
    """Runs the full golden test suite dynamically and updates benchmark scores."""
    try:
        security.require_permission(Permission.RUN_INVESTIGATION)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    report = await SystemEvaluator.evaluate_full_gridlens()
    return report
