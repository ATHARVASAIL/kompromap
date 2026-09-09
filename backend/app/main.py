"""FastAPI application entrypoint for Kompromap."""
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    correlation,
    dedup,
    edges,
    engagements,
    finding_gen,
    findings,
    graph,
    health,
    ingest,
    knowledge,
    nodes,
    pathfind,
    reporting,
    snapshots,
    triage,
)
from app.core.config import get_settings
from app.core.security import require_api_key

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Attack-chain graph builder for VAPT engagements.",
    version="0.1.0",
    docs_url=None if settings.api_key and not settings.debug else "/docs",
    redoc_url=None if settings.api_key and not settings.debug else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")

_protected = [
    finding_gen.router,
    correlation.router,
    dedup.router,
    engagements.router,
    snapshots.router,
    nodes.router,
    edges.router,
    findings.router,
    ingest.router,
    graph.router,
    pathfind.router,
    reporting.router,
    triage.router,
    knowledge.router,
]
for _router in _protected:
    app.include_router(_router, prefix="/api", dependencies=[Depends(require_api_key)])


@app.get("/")
def root() -> dict:
    return {"name": settings.app_name, "status": "running"}
