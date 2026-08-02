"""FastAPI application entrypoint for Kompromap."""
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import edges, engagements, findings, graph, health, ingest, nodes, pathfind, reporting, snapshots
from app.core.config import get_settings
from app.core.security import require_api_key

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Attack-chain graph builder for VAPT engagements.",
    version="0.1.0",
    # Interactive docs are handy locally but they advertise the full API
    # surface, so they're disabled once auth is switched on (i.e. any
    # non-local deployment). Flip DEBUG on to get them back.
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

# Health checks stay unauthenticated so Docker/load-balancer probes work
# without embedding a credential in orchestrator config. They expose
# nothing beyond "the process is up" and "the DB is reachable".
app.include_router(health.router, prefix="/api")

# Everything else is gated by require_api_key, which is a no-op unless
# API_KEY is configured — see app/core/security.py.
_protected = [
    engagements.router,
    snapshots.router,
    nodes.router,
    edges.router,
    findings.router,
    ingest.router,
    graph.router,
    pathfind.router,
    reporting.router,
]
for _router in _protected:
    app.include_router(_router, prefix="/api", dependencies=[Depends(require_api_key)])


@app.get("/")
def root() -> dict:
    return {"name": settings.app_name, "status": "running"}
