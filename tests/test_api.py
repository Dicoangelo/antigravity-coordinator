"""Tests for the FastAPI server."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from coordinator.api.server import app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_health() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "uptime_seconds" in data


@pytest.mark.anyio
async def test_coordinate_requires_task() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/coordinate", json={"strategy": "research"})
    assert response.status_code == 200
    data = response.json()
    assert "error" in data


@pytest.mark.anyio
async def test_coordinate_starts_session() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/coordinate",
            json={"strategy": "research", "task": "explore codebase"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"
    assert data["strategy"] == "research"
    assert "session_id" in data


@pytest.mark.anyio
async def test_status() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "active_agents" in data
    assert "count" in data


@pytest.mark.anyio
async def test_history() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/history")
    assert response.status_code == 200
    data = response.json()
    assert "outcomes" in data


@pytest.mark.anyio
async def test_metrics() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "avg_dq_score" in data
    assert "target_accuracy" in data
