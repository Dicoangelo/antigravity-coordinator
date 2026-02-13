"""Tests for the SQLite storage layer."""

from pathlib import Path

from coordinator.storage.database import Database


def test_ensure_tables(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    assert db.db_path.exists()


def test_wal_mode(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    with db.connect() as conn:
        result = conn.execute("PRAGMA journal_mode").fetchone()
        assert result[0] == "wal"


def test_insert_session(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    db.execute_insert(
        "INSERT INTO sessions (session_id, strategy, task) VALUES (?, ?, ?)",
        ("test-001", "research", "explore codebase"),
    )
    rows = db.execute("SELECT * FROM sessions WHERE session_id = ?", ("test-001",))
    assert len(rows) == 1
    assert rows[0]["strategy"] == "research"


def test_upsert_session(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    db.execute_insert(
        "INSERT INTO sessions (session_id, strategy, task) VALUES (?, ?, ?)",
        ("test-002", "research", "task A"),
    )
    db.execute_insert(
        """INSERT INTO sessions (session_id, strategy, task, status)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(session_id) DO UPDATE SET
             status = excluded.status,
             task = excluded.task""",
        ("test-002", "research", "task B", "completed"),
    )
    rows = db.execute("SELECT * FROM sessions WHERE session_id = ?", ("test-002",))
    assert len(rows) == 1
    assert rows[0]["status"] == "completed"
    assert rows[0]["task"] == "task B"


def test_insert_dq_score(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    db.execute_insert(
        """INSERT INTO dq_scores
           (query_hash, query_preview, complexity, model, dq_score, validity, specificity, correctness)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("abc123", "Design a system", 0.85, "opus", 0.84, 0.97, 1.0, 0.5),
    )
    rows = db.execute("SELECT * FROM dq_scores WHERE query_hash = ?", ("abc123",))
    assert len(rows) == 1
    assert rows[0]["model"] == "opus"
    assert rows[0]["dq_score"] == 0.84


def test_schema_version(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    rows = db.execute("SELECT version FROM schema_version")
    assert len(rows) == 1
    assert rows[0]["version"] == 1
