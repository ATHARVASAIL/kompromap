"""FastAPI application entrypoint for Kompromap."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import edges, engagements, findings, graph, health, ingest, nodes, pathfind, reporting, snapshots
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Attack-chain graph builder for VAPT engagements.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(engagements.router, prefix="/api")
app.include_router(snapshots.router, prefix="/api")
app.include_router(nodes.router, prefix="/api")
app.include_router(edges.router, prefix="/api")
app.include_router(findings.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")
app.include_router(graph.router, prefix="/api")
app.include_router(pathfind.router, prefix="/api")
app.include_router(reporting.router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {"name": settings.app_name, "status": "running", "docs": "/docs"}
