"""Tests for safety modules."""

from __future__ import annotations

import time

import pytest

from coordinator.safety import Guardrails, GuardrailResult


class TestGuardrails:
    """Test safety guardrails."""

    def test_cost_within_limit(self) -> None:
        """Test cost check when within limit."""
        guardrails = Guardrails(max_cost=100.0)
        result = guardrails.check_cost(50.0)

        assert result.passed is True
        assert result.violation is None
        assert result.action == "continue"

    def test_cost_exceeds_limit(self) -> None:
        """Test cost check when limit exceeded."""
        guardrails = Guardrails(max_cost=100.0)
        result = guardrails.check_cost(150.0)

        assert result.passed is False
        assert result.violation is not None
        assert "exceeded" in result.violation.lower()
        assert result.action == "kill"

    def test_cost_approaching_limit(self) -> None:
        """Test cost check when approaching limit (80% threshold)."""
        guardrails = Guardrails(max_cost=100.0)
        result = guardrails.check_cost(85.0)

        assert result.passed is True
        assert result.violation is not None
        assert "approaching" in result.violation.lower()
        assert result.action == "warn"

    def test_cost_no_limit(self) -> None:
        """Test cost check when no limit set."""
        guardrails = Guardrails(max_cost=None)
        result = guardrails.check_cost(999999.0)

        assert result.passed is True
        assert result.violation is None
        assert result.action == "continue"

    def test_duration_within_limit(self) -> None:
        """Test duration check when within limit."""
        guardrails = Guardrails(max_duration=300)
        result = guardrails.check_duration(150)

        assert result.passed is True
        assert result.violation is None
        assert result.action == "continue"

    def test_duration_exceeds_limit(self) -> None:
        """Test duration check when limit exceeded."""
        guardrails = Guardrails(max_duration=300)
        result = guardrails.check_duration(400)

        assert result.passed is False
        assert result.violation is not None
        assert "exceeded" in result.violation.lower()
        assert result.action == "kill"

    def test_duration_approaching_limit(self) -> None:
        """Test duration check when approaching limit (80% threshold)."""
        guardrails = Guardrails(max_duration=300)
        result = guardrails.check_duration(250)

        assert result.passed is True
        assert result.violation is not None
        assert "approaching" in result.violation.lower()
        assert result.action == "warn"

    def test_scope_allowed(self) -> None:
        """Test scope check for allowed file path."""
        guardrails = Guardrails(allowed_globs=["src/**/*.py", "tests/**/*.py"])
        result = guardrails.check_scope("src/coordinator/main.py")

        assert result.passed is True
        assert result.violation is None
        assert result.action == "continue"

    def test_scope_denied(self) -> None:
        """Test scope check for denied file path."""
        guardrails = Guardrails(allowed_globs=["src/**/*.py", "tests/**/*.py"])
        result = guardrails.check_scope("/etc/passwd")

        assert result.passed is False
        assert result.violation is not None
        assert "outside allowed scope" in result.violation.lower()
        assert result.action == "kill"

    def test_scope_no_restriction(self) -> None:
        """Test scope check when no restrictions set."""
        guardrails = Guardrails(allowed_globs=None)
        result = guardrails.check_scope("/any/path/file.txt")

        assert result.passed is True
        assert result.violation is None
        assert result.action == "continue"

    def test_heartbeat_within_timeout(self) -> None:
        """Test heartbeat check when within timeout."""
        guardrails = Guardrails(heartbeat_timeout=60)
        now = time.time()
        last_heartbeat = now - 30

        result = guardrails.check_heartbeat(last_heartbeat, now)

        assert result.passed is True
        assert result.violation is None
        assert result.action == "continue"

    def test_heartbeat_exceeds_timeout(self) -> None:
        """Test heartbeat check when timeout exceeded."""
        guardrails = Guardrails(heartbeat_timeout=60)
        now = time.time()
        last_heartbeat = now - 90

        result = guardrails.check_heartbeat(last_heartbeat, now)

        assert result.passed is False
        assert result.violation is not None
        assert "timeout" in result.violation.lower()
        assert result.action == "kill"

    def test_heartbeat_approaching_timeout(self) -> None:
        """Test heartbeat check when approaching timeout (80% threshold)."""
        guardrails = Guardrails(heartbeat_timeout=60)
        now = time.time()
        last_heartbeat = now - 50

        result = guardrails.check_heartbeat(last_heartbeat, now)

        assert result.passed is True
        assert result.violation is not None
        assert "approaching" in result.violation.lower()
        assert result.action == "warn"

    def test_check_all(self) -> None:
        """Test running all guardrail checks."""
        guardrails = Guardrails(
            max_cost=100.0,
            max_duration=300,
            allowed_globs=["src/**/*.py"],
            heartbeat_timeout=60,
        )

        now = time.time()
        results = guardrails.check_all(
            current_cost=50.0,
            elapsed_seconds=150,
            file_path="src/main.py",
            last_heartbeat=now - 30,
            now=now,
        )

        # Should return 4 results (cost, duration, heartbeat, scope)
        assert len(results) == 4
        assert all(r.passed for r in results)

    def test_check_all_with_violations(self) -> None:
        """Test check_all with multiple violations."""
        guardrails = Guardrails(
            max_cost=100.0,
            max_duration=300,
            allowed_globs=["src/**/*.py"],
            heartbeat_timeout=60,
        )

        now = time.time()
        results = guardrails.check_all(
            current_cost=150.0,  # Over limit
            elapsed_seconds=400,  # Over limit
            file_path="/etc/passwd",  # Outside scope
            last_heartbeat=now - 90,  # Timeout
            now=now,
        )

        # All should fail
        assert len(results) == 4
        assert all(not r.passed for r in results)
        assert all(r.action == "kill" for r in results)

    def test_check_all_without_scope(self) -> None:
        """Test check_all without file path (skips scope check)."""
        guardrails = Guardrails(
            max_cost=100.0,
            max_duration=300,
            allowed_globs=["src/**/*.py"],
            heartbeat_timeout=60,
        )

        now = time.time()
        results = guardrails.check_all(
            current_cost=50.0,
            elapsed_seconds=150,
            file_path=None,  # Skip scope check
            last_heartbeat=now - 30,
            now=now,
        )

        # Should return 3 results (cost, duration, heartbeat)
        assert len(results) == 3
        assert all(r.passed for r in results)

    def test_multiple_glob_patterns(self) -> None:
        """Test scope check with multiple glob patterns."""
        guardrails = Guardrails(
            allowed_globs=["src/**/*.py", "tests/**/*.py", "*.md"]
        )

        assert guardrails.check_scope("src/main.py").passed
        assert guardrails.check_scope("tests/test_main.py").passed
        assert guardrails.check_scope("README.md").passed
        assert not guardrails.check_scope("config.json").passed

    def test_exact_threshold_boundaries(self) -> None:
        """Test exact 80% threshold boundaries."""
        guardrails = Guardrails(max_cost=100.0, max_duration=100)

        # Exactly at 80%
        cost_result = guardrails.check_cost(80.0)
        duration_result = guardrails.check_duration(80)

        assert cost_result.passed is True
        assert cost_result.action == "warn"
        assert duration_result.passed is True
        assert duration_result.action == "warn"

        # Just below 80%
        cost_result = guardrails.check_cost(79.9)
        duration_result = guardrails.check_duration(79)

        assert cost_result.passed is True
        assert cost_result.action == "continue"
        assert duration_result.passed is True
        assert duration_result.action == "continue"
