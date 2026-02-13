"""SQLite database with WAL mode and connection pooling."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class Database:
    """SQLite storage layer with WAL mode for the coordinator."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or Path.home() / ".coordinator"
        self.db_path = self.data_dir / "data" / "coordinator.db"

    def _ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "data").mkdir(exist_ok=True)
        (self.data_dir / "logs").mkdir(exist_ok=True)

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with WAL mode."""
        self._ensure_dirs()
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def ensure_tables(self) -> None:
        """Create all tables if they don't exist."""
        with self.connect() as conn:
            conn.executescript(_SCHEMA)

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        """Execute a query and return results."""
        with self.connect() as conn:
            cursor = conn.execute(sql, params)
            return cursor.fetchall()

    def execute_insert(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        """Execute an insert and return lastrowid."""
        with self.connect() as conn:
            cursor = conn.execute(sql, params)
            return cursor.lastrowid or 0


_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    strategy TEXT NOT NULL,
    task TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT UNIQUE NOT NULL,
    session_id TEXT NOT NULL,
    model TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    started_at TEXT,
    completed_at TEXT,
    output TEXT
);

CREATE TABLE IF NOT EXISTS outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    outcome TEXT NOT NULL,
    quality REAL NOT NULL DEFAULT 0.0,
    complexity REAL NOT NULL DEFAULT 0.0,
    model_efficiency REAL NOT NULL DEFAULT 0.0,
    dq_score REAL NOT NULL DEFAULT 0.0,
    confidence REAL NOT NULL DEFAULT 0.0,
    agent_contributions TEXT DEFAULT '{}',
    analyzed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS baselines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL,
    parameters TEXT NOT NULL,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    confidence REAL NOT NULL DEFAULT 0.0,
    lineage TEXT DEFAULT '[]',
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    detected_pattern TEXT NOT NULL,
    confidence REAL NOT NULL,
    selected_strategy TEXT NOT NULL,
    detected_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS dq_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    query_hash TEXT NOT NULL,
    query_preview TEXT NOT NULL,
    complexity REAL NOT NULL,
    model TEXT NOT NULL,
    dq_score REAL NOT NULL,
    validity REAL NOT NULL DEFAULT 0.0,
    specificity REAL NOT NULL DEFAULT 0.0,
    correctness REAL NOT NULL DEFAULT 0.0,
    scored_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO schema_version (version) VALUES (1);
"""
