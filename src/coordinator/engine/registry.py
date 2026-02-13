"""Agent Registry - Tracks active agents, their state, progress, and cleanup."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from coordinator.storage.database import Database


class AgentState(StrEnum):
    """Agent execution states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class AgentRecord:
    """Record of an active or completed agent."""

    agent_id: str
    task_id: str  # Parent coordination task
    subtask: str
    agent_type: str  # explore, general-purpose, Bash, Plan
    model: str  # haiku, sonnet, opus
    state: str
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    files_locked: list[str] | None = None
    progress: float = 0.0  # 0-1
    last_heartbeat: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    dq_score: float = 0.5
    cost_estimate: float = 0.0

    def __post_init__(self) -> None:
        if self.files_locked is None:
            self.files_locked = []


class AgentRegistry:
    """
    Manages active agent tracking with database persistence.

    Features:
    - Database-backed storage with WAL mode
    - Heartbeat monitoring for stale agent detection
    - Automatic cleanup of completed/failed agents
    """

    # Timeout thresholds
    HEARTBEAT_TIMEOUT = 60  # seconds - mark stale after this
    AGENT_TIMEOUT = 300  # seconds - default max runtime
    STALE_CLEANUP = 600  # seconds - auto-cleanup after this

    def __init__(self, data_dir: Path | None = None) -> None:
        self.db = Database(data_dir)
        self.db.ensure_tables()
        self._ensure_agents_table()

    def _ensure_agents_table(self) -> None:
        """Create agents tracking table if needed (extends base schema)."""
        with self.db.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_registry (
                    agent_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    subtask TEXT NOT NULL,
                    agent_type TEXT NOT NULL,
                    model TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    files_locked TEXT DEFAULT '[]',
                    progress REAL DEFAULT 0.0,
                    last_heartbeat TEXT,
                    result TEXT,
                    error TEXT,
                    dq_score REAL DEFAULT 0.5,
                    cost_estimate REAL DEFAULT 0.0
                )
                """
            )

    def register(
        self,
        task_id: str,
        subtask: str,
        agent_type: str,
        model: str = "sonnet",
        files_to_lock: list[str] | None = None,
        dq_score: float = 0.5,
        cost_estimate: float = 0.0,
    ) -> str:
        """
        Register a new agent.

        Returns:
            agent_id: Unique identifier for the agent
        """
        import uuid

        agent_id = f"agent-{uuid.uuid4().hex[:8]}"

        files_json = json.dumps(files_to_lock or [])
        now = datetime.now().isoformat()

        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_registry (
                    agent_id, task_id, subtask, agent_type, model, state,
                    created_at, files_locked, dq_score, cost_estimate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_id,
                    task_id,
                    subtask,
                    agent_type,
                    model,
                    AgentState.PENDING.value,
                    now,
                    files_json,
                    dq_score,
                    cost_estimate,
                ),
            )

        return agent_id

    def start(self, agent_id: str) -> None:
        """Mark agent as started."""
        now = datetime.now().isoformat()
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE agent_registry
                SET state = ?, started_at = ?, last_heartbeat = ?
                WHERE agent_id = ?
                """,
                (AgentState.RUNNING.value, now, now, agent_id),
            )

    def heartbeat(self, agent_id: str, progress: float | None = None) -> None:
        """Update agent heartbeat."""
        now = datetime.now().isoformat()
        if progress is not None:
            progress = min(1.0, max(0.0, progress))
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE agent_registry SET last_heartbeat = ?, progress = ? WHERE agent_id = ?",
                    (now, progress, agent_id),
                )
        else:
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE agent_registry SET last_heartbeat = ? WHERE agent_id = ?",
                    (now, agent_id),
                )

    def complete(self, agent_id: str, result: dict[str, Any] | None = None) -> None:
        """Mark agent as completed."""
        now = datetime.now().isoformat()
        result_json = json.dumps(result) if result else None
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE agent_registry
                SET state = ?, completed_at = ?, progress = 1.0, result = ?
                WHERE agent_id = ?
                """,
                (AgentState.COMPLETED.value, now, result_json, agent_id),
            )
        agent = self.get(agent_id)
        if agent:
            self._log_outcome(agent)

    def fail(self, agent_id: str, error: str) -> None:
        """Mark agent as failed."""
        now = datetime.now().isoformat()
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE agent_registry
                SET state = ?, completed_at = ?, error = ?
                WHERE agent_id = ?
                """,
                (AgentState.FAILED.value, now, error, agent_id),
            )
        agent = self.get(agent_id)
        if agent:
            self._log_outcome(agent)

    def timeout(self, agent_id: str) -> None:
        """Mark agent as timed out."""
        now = datetime.now().isoformat()
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE agent_registry
                SET state = ?, completed_at = ?, error = ?
                WHERE agent_id = ?
                """,
                (AgentState.TIMEOUT.value, now, "Agent timed out", agent_id),
            )
        agent = self.get(agent_id)
        if agent:
            self._log_outcome(agent)

    def cancel(self, agent_id: str) -> None:
        """Cancel an agent."""
        now = datetime.now().isoformat()
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE agent_registry
                SET state = ?, completed_at = ?
                WHERE agent_id = ?
                """,
                (AgentState.CANCELLED.value, now, agent_id),
            )
        agent = self.get(agent_id)
        if agent:
            self._log_outcome(agent)

    def get(self, agent_id: str) -> AgentRecord | None:
        """Get agent by ID."""
        rows = self.db.execute("SELECT * FROM agent_registry WHERE agent_id = ?", (agent_id,))
        if rows:
            return self._row_to_record(rows[0])
        return None

    def get_task_agents(self, task_id: str) -> list[AgentRecord]:
        """Get all agents for a coordination task."""
        rows = self.db.execute("SELECT * FROM agent_registry WHERE task_id = ?", (task_id,))
        return [self._row_to_record(row) for row in rows]

    def get_active(self) -> list[AgentRecord]:
        """Get all running agents."""
        rows = self.db.execute(
            "SELECT * FROM agent_registry WHERE state IN (?, ?)",
            (AgentState.PENDING.value, AgentState.RUNNING.value),
        )
        return [self._row_to_record(row) for row in rows]

    def get_stale(self) -> list[AgentRecord]:
        """Get agents with stale heartbeats."""
        rows = self.db.execute(
            "SELECT * FROM agent_registry WHERE state = ?", (AgentState.RUNNING.value,)
        )
        now = time.time()
        stale = []

        for row in rows:
            last_hb = row["last_heartbeat"]
            if last_hb:
                hb_time = datetime.fromisoformat(last_hb).timestamp()
                if now - hb_time > self.HEARTBEAT_TIMEOUT:
                    stale.append(self._row_to_record(row))

        return stale

    def cleanup_completed(self, older_than_seconds: int | None = None) -> int:
        """Remove completed/failed agents from active tracking."""
        if older_than_seconds is None:
            older_than_seconds = self.STALE_CLEANUP

        cutoff_time = datetime.fromtimestamp(time.time() - older_than_seconds).isoformat()

        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM agent_registry
                WHERE state IN (?, ?, ?, ?)
                AND completed_at IS NOT NULL
                AND completed_at < ?
                """,
                (
                    AgentState.COMPLETED.value,
                    AgentState.FAILED.value,
                    AgentState.TIMEOUT.value,
                    AgentState.CANCELLED.value,
                    cutoff_time,
                ),
            )
            return cursor.rowcount

    def _log_outcome(self, agent: AgentRecord) -> None:
        """Log agent outcome to the agents table in the database."""
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO agents (
                    agent_id, session_id, model, role,
                    status, started_at, completed_at, output
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    status = excluded.status,
                    completed_at = excluded.completed_at,
                    output = excluded.output
                """,
                (
                    agent.agent_id,
                    agent.task_id,
                    agent.model,
                    agent.agent_type,
                    agent.state,
                    agent.started_at,
                    agent.completed_at,
                    json.dumps(asdict(agent)),
                ),
            )

    def _row_to_record(self, row: Any) -> AgentRecord:
        """Convert database row to AgentRecord."""
        return AgentRecord(
            agent_id=row["agent_id"],
            task_id=row["task_id"],
            subtask=row["subtask"],
            agent_type=row["agent_type"],
            model=row["model"],
            state=row["state"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            files_locked=json.loads(row["files_locked"]) if row["files_locked"] else [],
            progress=row["progress"],
            last_heartbeat=row["last_heartbeat"],
            result=json.loads(row["result"]) if row["result"] else None,
            error=row["error"],
            dq_score=row["dq_score"],
            cost_estimate=row["cost_estimate"],
        )

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        rows = self.db.execute("SELECT * FROM agent_registry")

        by_state: dict[str, int] = {}
        by_model: dict[str, int] = {}
        total_cost = 0.0

        for row in rows:
            state = row["state"]
            model = row["model"]
            cost = row["cost_estimate"]

            by_state[state] = by_state.get(state, 0) + 1
            by_model[model] = by_model.get(model, 0) + 1
            total_cost += cost

        return {
            "total_agents": len(rows),
            "by_state": by_state,
            "by_model": by_model,
            "total_cost_estimate": total_cost,
            "active_count": len(self.get_active()),
            "stale_count": len(self.get_stale()),
        }
