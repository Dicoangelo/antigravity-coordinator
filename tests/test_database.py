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


# --- Agents table CRUD ---


def test_insert_agent(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    db.execute_insert(
        """INSERT INTO agents (agent_id, session_id, model, role)
           VALUES (?, ?, ?, ?)""",
        ("agent-001", "sess-001", "opus", "researcher"),
    )
    rows = db.execute("SELECT * FROM agents WHERE agent_id = ?", ("agent-001",))
    assert len(rows) == 1
    assert rows[0]["model"] == "opus"
    assert rows[0]["role"] == "researcher"
    assert rows[0]["status"] == "pending"


def test_update_agent(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    db.execute_insert(
        """INSERT INTO agents (agent_id, session_id, model, role)
           VALUES (?, ?, ?, ?)""",
        ("agent-002", "sess-001", "sonnet", "builder"),
    )
    db.execute(
        """UPDATE agents SET status = ?, output = ? WHERE agent_id = ?""",
        ("completed", "built feature X", "agent-002"),
    )
    rows = db.execute("SELECT * FROM agents WHERE agent_id = ?", ("agent-002",))
    assert rows[0]["status"] == "completed"
    assert rows[0]["output"] == "built feature X"


def test_upsert_agent(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    db.execute_insert(
        """INSERT INTO agents (agent_id, session_id, model, role)
           VALUES (?, ?, ?, ?)""",
        ("agent-003", "sess-001", "haiku", "reviewer"),
    )
    db.execute_insert(
        """INSERT INTO agents (agent_id, session_id, model, role, status)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(agent_id) DO UPDATE SET
             status = excluded.status""",
        ("agent-003", "sess-001", "haiku", "reviewer", "running"),
    )
    rows = db.execute("SELECT * FROM agents WHERE agent_id = ?", ("agent-003",))
    assert len(rows) == 1
    assert rows[0]["status"] == "running"


def test_delete_agent(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    db.execute_insert(
        """INSERT INTO agents (agent_id, session_id, model, role)
           VALUES (?, ?, ?, ?)""",
        ("agent-del", "sess-001", "opus", "researcher"),
    )
    db.execute("DELETE FROM agents WHERE agent_id = ?", ("agent-del",))
    rows = db.execute("SELECT * FROM agents WHERE agent_id = ?", ("agent-del",))
    assert len(rows) == 0


# --- Outcomes table CRUD ---


def test_insert_outcome(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    db.execute_insert(
        """INSERT INTO outcomes
           (session_id, outcome, quality, complexity, model_efficiency, dq_score, confidence)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("sess-010", "success", 4.5, 0.7, 0.9, 0.85, 0.92),
    )
    rows = db.execute("SELECT * FROM outcomes WHERE session_id = ?", ("sess-010",))
    assert len(rows) == 1
    assert rows[0]["outcome"] == "success"
    assert rows[0]["quality"] == 4.5
    assert rows[0]["dq_score"] == 0.85


def test_upsert_outcome(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    db.execute_insert(
        """INSERT INTO outcomes
           (session_id, outcome, quality, complexity, model_efficiency, dq_score, confidence)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("sess-011", "partial", 2.0, 0.5, 0.6, 0.55, 0.4),
    )
    db.execute_insert(
        """INSERT INTO outcomes
           (session_id, outcome, quality, complexity, model_efficiency, dq_score, confidence)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(session_id) DO UPDATE SET
             outcome = excluded.outcome,
             quality = excluded.quality,
             dq_score = excluded.dq_score""",
        ("sess-011", "success", 4.0, 0.5, 0.6, 0.80, 0.4),
    )
    rows = db.execute("SELECT * FROM outcomes WHERE session_id = ?", ("sess-011",))
    assert len(rows) == 1
    assert rows[0]["outcome"] == "success"
    assert rows[0]["quality"] == 4.0
    assert rows[0]["dq_score"] == 0.80


def test_delete_outcome(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    db.execute_insert(
        """INSERT INTO outcomes
           (session_id, outcome, quality, complexity, model_efficiency, dq_score, confidence)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("sess-del", "failed", 1.0, 0.3, 0.2, 0.25, 0.1),
    )
    db.execute("DELETE FROM outcomes WHERE session_id = ?", ("sess-del",))
    rows = db.execute("SELECT * FROM outcomes WHERE session_id = ?", ("sess-del",))
    assert len(rows) == 0


# --- Baselines table CRUD ---


def test_insert_baseline(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    row_id = db.execute_insert(
        """INSERT INTO baselines (version, parameters, evidence_count, confidence)
           VALUES (?, ?, ?, ?)""",
        ("v1.0", '{"threshold": 0.7}', 50, 0.85),
    )
    assert row_id > 0
    rows = db.execute("SELECT * FROM baselines WHERE id = ?", (row_id,))
    assert len(rows) == 1
    assert rows[0]["version"] == "v1.0"
    assert rows[0]["evidence_count"] == 50
    assert rows[0]["confidence"] == 0.85


def test_update_baseline(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    row_id = db.execute_insert(
        """INSERT INTO baselines (version, parameters, evidence_count, confidence)
           VALUES (?, ?, ?, ?)""",
        ("v1.1", '{"threshold": 0.75}', 100, 0.90),
    )
    db.execute(
        """UPDATE baselines SET confidence = ?, evidence_count = ? WHERE id = ?""",
        (0.95, 150, row_id),
    )
    rows = db.execute("SELECT * FROM baselines WHERE id = ?", (row_id,))
    assert rows[0]["confidence"] == 0.95
    assert rows[0]["evidence_count"] == 150


def test_delete_baseline(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    row_id = db.execute_insert(
        """INSERT INTO baselines (version, parameters, evidence_count, confidence)
           VALUES (?, ?, ?, ?)""",
        ("v0.9", '{}', 10, 0.3),
    )
    db.execute("DELETE FROM baselines WHERE id = ?", (row_id,))
    rows = db.execute("SELECT * FROM baselines WHERE id = ?", (row_id,))
    assert len(rows) == 0


# --- Patterns table CRUD ---


def test_insert_pattern(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    row_id = db.execute_insert(
        """INSERT INTO patterns (session_id, detected_pattern, confidence, selected_strategy)
           VALUES (?, ?, ?, ?)""",
        ("sess-020", "debugging", 0.85, "review-build"),
    )
    assert row_id > 0
    rows = db.execute("SELECT * FROM patterns WHERE id = ?", (row_id,))
    assert len(rows) == 1
    assert rows[0]["detected_pattern"] == "debugging"
    assert rows[0]["confidence"] == 0.85
    assert rows[0]["selected_strategy"] == "review-build"


def test_update_pattern(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    row_id = db.execute_insert(
        """INSERT INTO patterns (session_id, detected_pattern, confidence, selected_strategy)
           VALUES (?, ?, ?, ?)""",
        ("sess-021", "research", 0.6, "research"),
    )
    db.execute(
        """UPDATE patterns SET confidence = ?, selected_strategy = ? WHERE id = ?""",
        (0.9, "full", row_id),
    )
    rows = db.execute("SELECT * FROM patterns WHERE id = ?", (row_id,))
    assert rows[0]["confidence"] == 0.9
    assert rows[0]["selected_strategy"] == "full"


def test_delete_pattern(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    row_id = db.execute_insert(
        """INSERT INTO patterns (session_id, detected_pattern, confidence, selected_strategy)
           VALUES (?, ?, ?, ?)""",
        ("sess-022", "refactoring", 0.5, "implement"),
    )
    db.execute("DELETE FROM patterns WHERE id = ?", (row_id,))
    rows = db.execute("SELECT * FROM patterns WHERE id = ?", (row_id,))
    assert len(rows) == 0


# --- DQ Scores upsert and delete ---


def test_update_dq_score(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    row_id = db.execute_insert(
        """INSERT INTO dq_scores
           (query_hash, query_preview, complexity, model, dq_score, validity, specificity, correctness)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("hash-upd", "Refactor module", 0.6, "sonnet", 0.70, 0.8, 0.7, 0.6),
    )
    db.execute(
        """UPDATE dq_scores SET dq_score = ?, model = ? WHERE id = ?""",
        (0.90, "opus", row_id),
    )
    rows = db.execute("SELECT * FROM dq_scores WHERE id = ?", (row_id,))
    assert rows[0]["dq_score"] == 0.90
    assert rows[0]["model"] == "opus"


def test_delete_dq_score(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    row_id = db.execute_insert(
        """INSERT INTO dq_scores
           (query_hash, query_preview, complexity, model, dq_score, validity, specificity, correctness)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("hash-del", "Delete me", 0.1, "haiku", 0.30, 0.3, 0.3, 0.3),
    )
    db.execute("DELETE FROM dq_scores WHERE id = ?", (row_id,))
    rows = db.execute("SELECT * FROM dq_scores WHERE id = ?", (row_id,))
    assert len(rows) == 0


# --- Foreign keys and directory structure ---


def test_directory_structure(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    assert (tmp_path / "coord" / "data").is_dir()
    assert (tmp_path / "coord" / "logs").is_dir()


def test_idempotent_ensure_tables(tmp_path: Path) -> None:
    db = Database(data_dir=tmp_path / "coord")
    db.ensure_tables()
    db.ensure_tables()  # Should not raise
    rows = db.execute("SELECT version FROM schema_version")
    assert len(rows) == 1
