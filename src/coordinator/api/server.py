"""FastAPI server for programmatic coordinator access."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from typing import Any

import click
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from coordinator import __version__
from coordinator.storage.database import Database

app = FastAPI(
    title="Antigravity Coordinator API",
    version=__version__,
    description="Self-optimizing multi-agent coordination API",
)

_start_time = time.monotonic()
_db = Database()


@app.get("/api/health")
async def health() -> dict[str, Any]:
    """Health check."""
    uptime = time.monotonic() - _start_time
    return {"status": "ok", "version": __version__, "uptime_seconds": round(uptime, 1)}


@app.post("/api/coordinate")
async def coordinate(request: dict[str, Any]) -> dict[str, Any]:
    """Start a coordination session."""
    strategy = request.get("strategy", "auto")
    task = request.get("task", "")
    if not task:
        return {"error": "task is required"}
    return {
        "session_id": f"coord-{int(time.time())}",
        "strategy": strategy,
        "task": task,
        "status": "started",
    }


@app.get("/api/status")
async def status() -> dict[str, Any]:
    """Get active agents and their state."""
    try:
        rows = _db.execute(
            "SELECT agent_id, session_id, model, role, status FROM agents WHERE status = 'active'"
        )
        agents = [dict(row) for row in rows]
    except Exception:
        agents = []
    return {"active_agents": agents, "count": len(agents)}


@app.get("/api/history")
async def history(limit: int = 20, offset: int = 0) -> dict[str, Any]:
    """Get session outcomes with DQ scores."""
    try:
        rows = _db.execute(
            "SELECT * FROM outcomes ORDER BY analyzed_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        outcomes = [dict(row) for row in rows]
    except Exception:
        outcomes = []
    return {"outcomes": outcomes, "count": len(outcomes), "limit": limit, "offset": offset}


@app.get("/api/metrics")
async def metrics() -> dict[str, Any]:
    """Routing accuracy, cost efficiency, DQ trends."""
    try:
        rows = _db.execute("SELECT AVG(dq_score) as avg_dq, COUNT(*) as total FROM dq_scores")
        row = rows[0] if rows else None
        avg_dq = float(row["avg_dq"]) if row and row["avg_dq"] else 0.0
        total = int(row["total"]) if row else 0
    except Exception:
        avg_dq = 0.0
        total = 0
    return {
        "avg_dq_score": round(avg_dq, 3),
        "total_scores": total,
        "target_accuracy": 0.75,
        "target_cost_reduction": 0.20,
    }


@app.get("/api/stream")
async def stream() -> StreamingResponse:
    """SSE endpoint for real-time agent progress."""

    async def event_generator() -> AsyncGenerator[str, None]:
        while True:
            try:
                rows = _db.execute("SELECT agent_id, status FROM agents WHERE status = 'active'")
                agents = [dict(row) for row in rows]
            except Exception:
                agents = []
            yield f"data: {{'agents': {len(agents)}, 'timestamp': {time.time()}}}\n\n"
            await asyncio.sleep(3)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@click.command()
@click.option("--port", default=3848, help="Port to listen on")
@click.option("--host", default="127.0.0.1", help="Host to bind to")
def main(port: int, host: str) -> None:
    """Start the Coordinator API server."""
    import uvicorn

    uvicorn.run(app, host=host, port=port)
