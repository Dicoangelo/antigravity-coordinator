"""Conflict Manager - File locking to prevent write conflicts between agents."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from coordinator.storage.database import Database


class LockType(StrEnum):
    """File lock types."""

    READ = "read"
    WRITE = "write"


@dataclass
class FileLock:
    """A lock on a file."""

    path: str
    agent_id: str
    lock_type: str
    acquired_at: str
    expires_at: str | None = None


class ConflictManager:
    """
    Manages file locks for multi-agent coordination.

    Prevents:
    - Multiple writers to same file
    - Writers when readers exist
    - Readers when writer exists
    """

    # Lock timeout (auto-release stale locks)
    LOCK_TIMEOUT = 600  # 10 minutes

    def __init__(self, data_dir: Path | None = None) -> None:
        self.db = Database(data_dir)
        self.db.ensure_tables()
        self._ensure_locks_table()

    def _ensure_locks_table(self) -> None:
        """Create file locks table if needed."""
        with self.db.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS file_locks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    lock_type TEXT NOT NULL,
                    acquired_at TEXT NOT NULL,
                    expires_at TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_file_locks_path ON file_locks(path)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_file_locks_agent ON file_locks(agent_id)")

    def _normalize_path(self, path: str) -> str:
        """Normalize path for consistent comparison."""
        return str(Path(path).resolve())

    def _cleanup_expired(self) -> None:
        """Remove expired locks."""
        cutoff_time = datetime.fromtimestamp(time.time() - self.LOCK_TIMEOUT).isoformat()
        with self.db.connect() as conn:
            conn.execute("DELETE FROM file_locks WHERE acquired_at < ?", (cutoff_time,))

    def check_conflicts(
        self,
        paths: Sequence[str],
        lock_type: str,
        agent_id: str | None = None,
    ) -> list[tuple[str, str, str]]:
        """
        Check if acquiring locks would conflict.

        Args:
            paths: Files to check
            lock_type: "read" or "write"
            agent_id: Agent requesting (to allow self-upgrade)

        Returns:
            List of (path, conflicting_agent_id, conflict_reason)
        """
        self._cleanup_expired()
        conflicts: list[tuple[str, str, str]] = []

        for path in paths:
            norm_path = self._normalize_path(path)
            rows = self.db.execute("SELECT * FROM file_locks WHERE path = ?", (norm_path,))

            for row in rows:
                # Skip own locks
                if agent_id and row["agent_id"] == agent_id:
                    continue

                # Write conflicts with everything
                if lock_type == LockType.WRITE.value:
                    conflicts.append(
                        (
                            path,
                            row["agent_id"],
                            f"File has existing {row['lock_type']} lock",
                        )
                    )
                    break

                # Read conflicts with write
                elif row["lock_type"] == LockType.WRITE.value:
                    conflicts.append((path, row["agent_id"], "File has existing write lock"))
                    break

        return conflicts

    def check_all(self, subtasks: Sequence[dict[str, Any]]) -> list[tuple[str, str, str]]:
        """
        Check all subtasks for file conflicts.

        Args:
            subtasks: List of subtask dicts with 'files' and 'lock_type' keys

        Returns:
            List of all conflicts found
        """
        all_conflicts: list[tuple[str, str, str]] = []

        for subtask in subtasks:
            files = subtask.get("files", [])
            lock_type = subtask.get("lock_type", LockType.READ.value)
            agent_id = subtask.get("agent_id")

            conflicts = self.check_conflicts(files, lock_type, agent_id)
            all_conflicts.extend(conflicts)

        return all_conflicts

    def acquire(self, path: str, agent_id: str, lock_type: str) -> bool:
        """
        Acquire a lock on a file.

        Args:
            path: File path
            agent_id: Agent ID
            lock_type: "read" or "write"

        Returns:
            True if acquired, False if conflict
        """
        norm_path = self._normalize_path(path)

        # Check conflicts first
        conflicts = self.check_conflicts([path], lock_type, agent_id)
        if conflicts:
            return False

        self._cleanup_expired()

        # Remove any existing lock by this agent (upgrade/downgrade)
        with self.db.connect() as conn:
            conn.execute(
                "DELETE FROM file_locks WHERE path = ? AND agent_id = ?",
                (norm_path, agent_id),
            )

            # Add lock
            conn.execute(
                """
                INSERT INTO file_locks (path, agent_id, lock_type, acquired_at)
                VALUES (?, ?, ?, ?)
                """,
                (norm_path, agent_id, lock_type, datetime.now().isoformat()),
            )

        return True

    def acquire_batch(
        self, files: Sequence[str], agent_id: str, lock_type: str
    ) -> tuple[bool, list[str]]:
        """
        Acquire locks on multiple files atomically.

        Returns:
            (success, list of failed files)
        """
        # Check all conflicts first
        conflicts = self.check_conflicts(files, lock_type, agent_id)
        if conflicts:
            return False, [c[0] for c in conflicts]

        # Acquire all
        for path in files:
            if not self.acquire(path, agent_id, lock_type):
                # Rollback acquired locks
                self.release_agent(agent_id)
                return False, [path]

        return True, []

    def release(self, path: str, agent_id: str) -> None:
        """Release a lock on a file."""
        norm_path = self._normalize_path(path)
        with self.db.connect() as conn:
            conn.execute(
                "DELETE FROM file_locks WHERE path = ? AND agent_id = ?",
                (norm_path, agent_id),
            )

    def release_agent(self, agent_id: str) -> None:
        """Release all locks held by an agent."""
        with self.db.connect() as conn:
            conn.execute("DELETE FROM file_locks WHERE agent_id = ?", (agent_id,))

    def get_agent_locks(self, agent_id: str) -> list[FileLock]:
        """Get all locks held by an agent."""
        rows = self.db.execute("SELECT * FROM file_locks WHERE agent_id = ?", (agent_id,))
        return [
            FileLock(
                path=row["path"],
                agent_id=row["agent_id"],
                lock_type=row["lock_type"],
                acquired_at=row["acquired_at"],
                expires_at=row["expires_at"],
            )
            for row in rows
        ]

    def get_file_locks(self, path: str) -> list[FileLock]:
        """Get all locks on a file."""
        norm_path = self._normalize_path(path)
        rows = self.db.execute("SELECT * FROM file_locks WHERE path = ?", (norm_path,))
        return [
            FileLock(
                path=row["path"],
                agent_id=row["agent_id"],
                lock_type=row["lock_type"],
                acquired_at=row["acquired_at"],
                expires_at=row["expires_at"],
            )
            for row in rows
        ]

    def cleanup_stale(self) -> int:
        """Remove all stale locks."""
        cutoff_time = datetime.fromtimestamp(time.time() - self.LOCK_TIMEOUT).isoformat()
        with self.db.connect() as conn:
            cursor = conn.execute("DELETE FROM file_locks WHERE acquired_at < ?", (cutoff_time,))
            return cursor.rowcount

    def get_stats(self) -> dict[str, Any]:
        """Get lock statistics."""
        rows = self.db.execute("SELECT * FROM file_locks")

        read_locks = sum(1 for row in rows if row["lock_type"] == LockType.READ.value)
        write_locks = len(rows) - read_locks

        agents = {row["agent_id"] for row in rows}
        paths = {row["path"] for row in rows}

        return {
            "total_locks": len(rows),
            "read_locks": read_locks,
            "write_locks": write_locks,
            "files_locked": len(paths),
            "agents_with_locks": len(agents),
        }


def detect_potential_conflicts(
    subtasks: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """
    Pre-flight check for potential conflicts between planned subtasks.

    Args:
        subtasks: List of subtasks with 'files' (list of paths) and 'lock_type'

    Returns:
        {
            "has_conflicts": bool,
            "can_parallelize": bool,
            "conflicts": [...],
            "parallel_groups": [[subtask_indices], ...]
        }
    """
    # Track which files each subtask needs
    file_usage: dict[str, list[tuple[int, str]]] = {}

    for idx, subtask in enumerate(subtasks):
        files = subtask.get("files", [])
        lock_type = subtask.get("lock_type", LockType.READ.value)

        for path in files:
            norm_path = str(Path(path).resolve())
            if norm_path not in file_usage:
                file_usage[norm_path] = []
            file_usage[norm_path].append((idx, lock_type))

    # Find conflicts
    conflicts: list[dict[str, Any]] = []
    conflicting_pairs: set[tuple[int, int]] = set()

    for path, usages in file_usage.items():
        if len(usages) <= 1:
            continue

        # Check each pair
        for i, (idx1, lock1) in enumerate(usages):
            for idx2, lock2 in usages[i + 1 :]:
                # Conflict if any is a writer
                if lock1 == LockType.WRITE.value or lock2 == LockType.WRITE.value:
                    conflicts.append(
                        {"path": path, "subtasks": [idx1, idx2], "locks": [lock1, lock2]}
                    )
                    conflicting_pairs.add((min(idx1, idx2), max(idx1, idx2)))

    # Build parallel groups (subtasks that don't conflict)
    n = len(subtasks)
    parallel_groups: list[list[int]] = []
    assigned: set[int] = set()

    for idx in range(n):
        if idx in assigned:
            continue

        # Start new group
        group = [idx]
        assigned.add(idx)

        # Try to add others that don't conflict with group
        for other in range(idx + 1, n):
            if other in assigned:
                continue

            # Check if other conflicts with anyone in group
            can_add = True
            for member in group:
                if (min(member, other), max(member, other)) in conflicting_pairs:
                    can_add = False
                    break

            if can_add:
                group.append(other)
                assigned.add(other)

        parallel_groups.append(group)

    return {
        "has_conflicts": len(conflicts) > 0,
        "can_parallelize": len(parallel_groups) > 0 and any(len(g) > 1 for g in parallel_groups),
        "conflicts": conflicts,
        "parallel_groups": parallel_groups,
    }
