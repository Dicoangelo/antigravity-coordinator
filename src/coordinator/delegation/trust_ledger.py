"""
Trust Ledger — Agent Trust Score Tracking with Bayesian Updates

Implements the trust system from arXiv:2602.11865 Section 4.6.

Uses Bayesian inference with Beta distribution for trust score updates:
- Prior: Beta(alpha=1, beta=1) for new agents -> E[Beta] = 0.5 (uninformative prior)
- Update: alpha = successes + 1, beta = failures + 1
- Trust score: E[Beta] = alpha/(alpha+beta)

Decay: trust_score *= 0.95 for entries not updated in 7+ days.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite


@dataclass
class AgentTrustScore:
    """Agent trust score with Bayesian statistics."""

    agent_id: str
    task_type: str
    success_count: int
    failure_count: int
    avg_quality: float
    avg_duration: float
    trust_score: float
    last_updated: str


class TrustLedger:
    """
    Persistent trust ledger with Bayesian trust score updates.

    Trust calculation (Bayesian):
    - alpha = success_count + 1
    - beta = failure_count + 1
    - trust_score = alpha / (alpha + beta)
    """

    DECAY_DAYS = 7
    DECAY_FACTOR = 0.95
    DB_PATH = Path.home() / ".agent-core" / "storage" / "trust_ledger.db"

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = Path(db_path) if db_path else self.DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db: Optional[aiosqlite.Connection] = None

    async def __aenter__(self) -> "TrustLedger":
        await self._init_db()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        await self.close()

    async def _init_db(self) -> None:
        self._db = await aiosqlite.connect(str(self.db_path))
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS trust_entries (
                agent_id TEXT NOT NULL,
                task_type TEXT NOT NULL,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                avg_quality REAL DEFAULT 0.0,
                avg_duration REAL DEFAULT 0.0,
                trust_score REAL DEFAULT 0.5,
                last_updated TEXT NOT NULL,
                PRIMARY KEY (agent_id, task_type),
                CHECK (success_count >= 0),
                CHECK (failure_count >= 0),
                CHECK (avg_quality BETWEEN 0.0 AND 1.0),
                CHECK (avg_duration >= 0.0),
                CHECK (trust_score BETWEEN 0.0 AND 1.0)
            )
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_trust_task_type
            ON trust_entries(task_type, trust_score DESC)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_trust_agent
            ON trust_entries(agent_id)
        """)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    async def record_outcome(
        self,
        agent_id: str,
        task_type: str,
        success: bool,
        quality: float,
        duration: float,
    ) -> float:
        """Record task outcome and update trust score using Bayesian inference."""
        if not 0.0 <= quality <= 1.0:
            raise ValueError(f"quality must be in [0.0, 1.0], got {quality}")
        if duration < 0.0:
            raise ValueError(f"duration must be >= 0.0, got {duration}")

        assert self._db is not None
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

        cursor = await self._db.execute(
            "SELECT success_count, failure_count, avg_quality, avg_duration "
            "FROM trust_entries WHERE agent_id = ? AND task_type = ?",
            (agent_id, task_type),
        )
        row = await cursor.fetchone()

        if row:
            success_count, failure_count, avg_quality, avg_duration = row
            total_tasks = success_count + failure_count

            if success:
                success_count += 1
            else:
                failure_count += 1

            new_total = total_tasks + 1
            avg_quality = (avg_quality * total_tasks + quality) / new_total
            avg_duration = (avg_duration * total_tasks + duration) / new_total
        else:
            success_count = 1 if success else 0
            failure_count = 0 if success else 1
            avg_quality = quality
            avg_duration = duration

        alpha = success_count + 1
        beta = failure_count + 1
        trust_score = alpha / (alpha + beta)

        await self._db.execute(
            """INSERT INTO trust_entries
               (agent_id, task_type, success_count, failure_count,
                avg_quality, avg_duration, trust_score, last_updated)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(agent_id, task_type) DO UPDATE SET
                   success_count = excluded.success_count,
                   failure_count = excluded.failure_count,
                   avg_quality = excluded.avg_quality,
                   avg_duration = excluded.avg_duration,
                   trust_score = excluded.trust_score,
                   last_updated = excluded.last_updated""",
            (
                agent_id,
                task_type,
                success_count,
                failure_count,
                avg_quality,
                avg_duration,
                trust_score,
                timestamp,
            ),
        )
        await self._db.commit()
        return trust_score

    async def get_trust_score(self, agent_id: str, task_type: str) -> float:
        """Get current trust score with time decay applied."""
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT trust_score, last_updated FROM trust_entries "
            "WHERE agent_id = ? AND task_type = ?",
            (agent_id, task_type),
        )
        row = await cursor.fetchone()
        if not row:
            return 0.5

        trust_score, last_updated = row
        last_updated_time = time.mktime(
            time.strptime(last_updated, "%Y-%m-%d %H:%M:%S")
        )
        days_since_update = (time.time() - last_updated_time) / (24 * 3600)

        if days_since_update >= self.DECAY_DAYS:
            trust_score *= self.DECAY_FACTOR
            trust_score = max(0.0, min(1.0, trust_score))

        return trust_score

    async def get_top_agents(
        self, task_type: Optional[str] = None, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get top-performing agents with time decay applied."""
        assert self._db is not None
        if task_type:
            cursor = await self._db.execute(
                "SELECT agent_id, trust_score, success_count, failure_count, "
                "avg_quality, avg_duration, last_updated "
                "FROM trust_entries WHERE task_type = ? ORDER BY trust_score DESC",
                (task_type,),
            )
        else:
            cursor = await self._db.execute(
                "SELECT agent_id, trust_score, success_count, failure_count, "
                "avg_quality, avg_duration, last_updated "
                "FROM trust_entries ORDER BY trust_score DESC"
            )
        rows = await cursor.fetchall()

        current_time = time.time()
        decayed_scores = []

        for row in rows:
            (
                agent_id,
                trust_score,
                success_count,
                failure_count,
                avg_quality,
                avg_duration,
                last_updated,
            ) = row
            last_updated_time = time.mktime(
                time.strptime(last_updated, "%Y-%m-%d %H:%M:%S")
            )
            days_since_update = (current_time - last_updated_time) / (24 * 3600)

            if days_since_update >= self.DECAY_DAYS:
                trust_score *= self.DECAY_FACTOR
                trust_score = max(0.0, min(1.0, trust_score))

            decayed_scores.append(
                {
                    "agent_id": agent_id,
                    "trust_score": trust_score,
                    "success_count": success_count,
                    "failure_count": failure_count,
                    "avg_quality": avg_quality,
                    "avg_duration": avg_duration,
                }
            )

        decayed_scores.sort(key=lambda x: x["trust_score"], reverse=True)
        return decayed_scores[:limit]

    async def get_agent_stats(
        self, agent_id: str, task_type: str
    ) -> Optional[AgentTrustScore]:
        """Get detailed statistics for an agent on a specific task type."""
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT agent_id, task_type, success_count, failure_count, "
            "avg_quality, avg_duration, trust_score, last_updated "
            "FROM trust_entries WHERE agent_id = ? AND task_type = ?",
            (agent_id, task_type),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        return AgentTrustScore(
            agent_id=row[0],
            task_type=row[1],
            success_count=row[2],
            failure_count=row[3],
            avg_quality=row[4],
            avg_duration=row[5],
            trust_score=row[6],
            last_updated=row[7],
        )
