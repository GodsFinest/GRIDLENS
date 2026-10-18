"""FastAPI Application Entry Point for GridLens."""
import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from apps.api.routers import (
    investigations,
    incidents,
    graph,
    validation,
    evaluation,
    actions,
    physics,
)

app = FastAPI(
    title="GridLens API",
    description="Power-system event investigation API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("GRIDLENS_ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-GridLens-API-Key"],
)

app.include_router(investigations.router, prefix="/api/v1")
app.include_router(incidents.router, prefix="/api/v1")
app.include_router(graph.router, prefix="/api/v1")
app.include_router(validation.router, prefix="/api/v1")
app.include_router(evaluation.router, prefix="/api/v1")
app.include_router(actions.router, prefix="/api/v1")
app.include_router(physics.router, prefix="/api/v1")


@app.get("/")
async def root_health_check():
    return {
        "status": "ONLINE",
        "service": "GridLens API",
        "substation": "Orion Grid Substation OGS-01",
        "version": "1.0.0",
        "docs_url": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("apps.api.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
