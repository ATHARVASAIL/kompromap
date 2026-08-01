from pydantic import BaseModel

from app.schemas.pathfind import PathResultResponse


class DashboardResponse(BaseModel):
    """Spec §5 Phase 4 / §7 Phase 6: "Dashboard: node/edge counts, number of
    paths to crown jewels, highest-ease chain found." """

    total_nodes: int
    total_edges: int
    node_counts_by_type: dict[str, int]
    edge_counts_by_type: dict[str, int]
    entry_point_count: int
    crown_jewel_count: int
    paths_to_crown_jewels_count: int
    highest_ease_chain: PathResultResponse | None
