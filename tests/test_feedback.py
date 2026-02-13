"""Tests for feedback module (ACE analyzer and optimizer)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from coordinator.feedback import (
    AnalysisResult,
    ConsensusResult,
    Optimizer,
    OptimizationProposal,
    analyze_complexity,
    analyze_productivity,
    assess_model_efficiency,
    assess_routing_quality,
    detect_outcome,
    score_quality,
    synthesize_consensus,
)
from coordinator.storage.database import Database


# ============================================================================
# ACE Analyzer Tests
# ============================================================================


def test_detect_outcome_success() -> None:
    """Test outcome detection for successful session."""
    session_data = {
        "messages": [{"role": "user", "content": "test"}] * 10,
        "errors": [],
        "tools": [
            {"name": "Read", "input": {}},
            {"name": "Write", "input": {}},
        ],
    }

    result = detect_outcome(session_data)

    assert isinstance(result, AnalysisResult)
    assert result.agent_name == "outcome_detector"
    assert result.data["outcome"] == "success"
    assert 0.0 <= result.dq_score <= 1.0
    assert 0.0 <= result.confidence <= 1.0


def test_detect_outcome_error() -> None:
    """Test outcome detection for error session."""
    session_data = {
        "messages": [{"role": "user", "content": "test"}] * 10,
        "errors": [{"message": "Error"}] * 6,
        "tools": [],
    }

    result = detect_outcome(session_data)

    assert result.data["outcome"] == "error"


def test_detect_outcome_research() -> None:
    """Test outcome detection for research session."""
    session_data = {
        "messages": [{"role": "user", "content": "test"}] * 10,
        "errors": [],
        "tools": [
            {"name": "Read", "input": {}},
            {"name": "Grep", "input": {}},
            {"name": "Glob", "input": {}},
        ],
    }

    result = detect_outcome(session_data)

    assert result.data["outcome"] == "research"


def test_detect_outcome_abandoned() -> None:
    """Test outcome detection for abandoned session."""
    session_data = {
        "messages": [{"role": "user", "content": "test"}] * 3,
        "errors": [],
        "tools": [],
    }

    result = detect_outcome(session_data)

    assert result.data["outcome"] == "abandoned"


def test_score_quality_high() -> None:
    """Test quality scoring for high-quality session."""
    session_data = {
        "messages": [{"role": "user", "content": "test"}] * 20,
        "errors": [],
        "tools": [],
    }

    result = score_quality(session_data)

    assert isinstance(result, AnalysisResult)
    assert result.agent_name == "quality_scorer"
    assert result.data["quality"] >= 4.0


def test_score_quality_low() -> None:
    """Test quality scoring for low-quality session."""
    session_data = {
        "messages": [{"role": "user", "content": "test"}] * 10,
        "errors": [{"message": "Error"}] * 5,
        "tools": [],
    }

    result = score_quality(session_data)

    assert result.data["quality"] < 3.0


def test_analyze_complexity_high() -> None:
    """Test complexity analysis for complex session."""
    session_data = {
        "messages": [{"role": "user", "content": "test"}] * 60,
        "tools": [{"name": "Read", "input": {}}] * 40,
    }

    result = analyze_complexity(session_data)

    assert isinstance(result, AnalysisResult)
    assert result.agent_name == "complexity_analyzer"
    assert result.data["complexity"] >= 0.7


def test_analyze_complexity_low() -> None:
    """Test complexity analysis for simple session."""
    session_data = {
        "messages": [{"role": "user", "content": "test"}] * 10,
        "tools": [{"name": "Read", "input": {}}] * 5,
    }

    result = analyze_complexity(session_data)

    assert result.data["complexity"] <= 0.5


def test_assess_model_efficiency_opus() -> None:
    """Test model efficiency for Opus on complex task."""
    session_data = {
        "messages": [{"role": "user", "content": "test"}] * 50,
        "tools": [],
        "metadata": {"model": "claude-opus-4"},
    }

    result = assess_model_efficiency(session_data)

    assert isinstance(result, AnalysisResult)
    assert result.agent_name == "model_efficiency"
    assert result.data["efficiency"] > 0.7
    assert result.data["optimal_model"] == "opus"


def test_assess_model_efficiency_haiku_simple() -> None:
    """Test model efficiency for Haiku on simple task."""
    session_data = {
        "messages": [{"role": "user", "content": "test"}] * 10,
        "tools": [],
        "metadata": {"model": "claude-haiku"},
    }

    result = assess_model_efficiency(session_data)

    assert result.data["efficiency"] > 0.5
    assert result.data["optimal_model"] == "haiku"


def test_assess_model_efficiency_haiku_complex() -> None:
    """Test model efficiency for Haiku on complex task (inefficient)."""
    session_data = {
        "messages": [{"role": "user", "content": "test"}] * 50,
        "tools": [],
        "metadata": {"model": "claude-haiku"},
    }

    result = assess_model_efficiency(session_data)

    assert result.data["efficiency"] < 0.5
    assert result.data["optimal_model"] == "sonnet"


def test_analyze_productivity_high() -> None:
    """Test productivity analysis for productive session."""
    session_data = {
        "messages": [{"role": "user", "content": "test"}] * 20,
        "tools": [
            {"name": "Write", "input": {}},
            {"name": "Edit", "input": {}},
            {"name": "Read", "input": {}},
        ],
    }

    result = analyze_productivity(session_data)

    assert isinstance(result, AnalysisResult)
    assert result.agent_name == "productivity_analyzer"
    assert result.data["productivity_score"] > 0.5
    assert result.data["level"] in ["High", "Moderate"]


def test_analyze_productivity_low() -> None:
    """Test productivity analysis for exploratory session."""
    session_data = {
        "messages": [{"role": "user", "content": "test"}] * 20,
        "tools": [
            {"name": "Read", "input": {}},
            {"name": "Grep", "input": {}},
            {"name": "Glob", "input": {}},
        ],
    }

    result = analyze_productivity(session_data)

    assert result.data["productivity_score"] < 0.5
    assert result.data["level"] == "Low"


def test_assess_routing_quality_good() -> None:
    """Test routing quality for well-routed session."""
    session_data = {
        "messages": [{"role": "user", "content": "test"}] * 50,
        "tools": [],
        "metadata": {"model": "claude-opus-4"},
    }

    result = assess_routing_quality(session_data)

    assert isinstance(result, AnalysisResult)
    assert result.agent_name == "routing_quality"
    assert result.data["routing_quality"] > 0.7


def test_assess_routing_quality_poor() -> None:
    """Test routing quality for poorly routed session."""
    session_data = {
        "messages": [{"role": "user", "content": "test"}] * 10,
        "tools": [],
        "metadata": {"model": "claude-opus-4"},
    }

    result = assess_routing_quality(session_data)

    assert result.data["routing_quality"] <= 0.7


def test_synthesize_consensus_empty() -> None:
    """Test consensus synthesis with no results."""
    consensus = synthesize_consensus([])

    assert isinstance(consensus, ConsensusResult)
    assert consensus.outcome == "unknown"
    assert consensus.quality == 3.0
    assert consensus.complexity == 0.5
    assert consensus.model_efficiency == 0.5


def test_synthesize_consensus_full() -> None:
    """Test consensus synthesis with all agents."""
    # Create synthetic results
    results = [
        AnalysisResult(
            agent_name="outcome_detector",
            summary="Success",
            dq_score=0.8,
            confidence=0.9,
            data={"outcome": "success"},
        ),
        AnalysisResult(
            agent_name="quality_scorer",
            summary="High quality",
            dq_score=0.7,
            confidence=0.8,
            data={"quality": 4.5},
        ),
        AnalysisResult(
            agent_name="complexity_analyzer",
            summary="Moderate",
            dq_score=0.6,
            confidence=0.7,
            data={"complexity": 0.6},
        ),
        AnalysisResult(
            agent_name="model_efficiency",
            summary="Efficient",
            dq_score=0.7,
            confidence=0.8,
            data={"efficiency": 0.85, "optimal_model": "sonnet"},
        ),
        AnalysisResult(
            agent_name="productivity_analyzer",
            summary="High",
            dq_score=0.6,
            confidence=0.7,
            data={"productivity_score": 0.75, "level": "High"},
        ),
        AnalysisResult(
            agent_name="routing_quality",
            summary="Good routing",
            dq_score=0.7,
            confidence=0.8,
            data={"routing_quality": 0.8},
        ),
    ]

    consensus = synthesize_consensus(results)

    assert consensus.outcome == "success"
    assert consensus.quality == 4.5
    assert consensus.complexity == 0.6
    assert consensus.model_efficiency == 0.85
    assert 0.0 <= consensus.dq_score <= 1.0
    assert 0.0 <= consensus.confidence <= 1.0


# ============================================================================
# Optimizer Tests
# ============================================================================


@pytest.fixture
def temp_db() -> Database:
    """Create temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Database(Path(tmpdir))
        db.ensure_tables()
        yield db


def test_optimizer_propose_insufficient_data(temp_db: Database) -> None:
    """Test that optimizer returns no proposals with insufficient data."""
    optimizer = Optimizer(temp_db)

    proposals = optimizer.propose()

    assert proposals == []


def test_optimizer_propose_with_data(temp_db: Database) -> None:
    """Test optimizer with sufficient session data."""
    # Insert 60 synthetic outcomes
    for i in range(60):
        temp_db.execute_insert(
            """
            INSERT INTO outcomes
            (session_id, outcome, quality, complexity, model_efficiency, dq_score, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"session-{i}",
                "success" if i % 2 == 0 else "partial",
                4.0 if i % 2 == 0 else 3.0,
                0.6,
                0.8,
                0.7,
                0.8,
            ),
        )

    optimizer = Optimizer(temp_db)
    proposals = optimizer.propose()

    # Should have proposals (if confidence > 75%)
    assert isinstance(proposals, list)
    for proposal in proposals:
        assert isinstance(proposal, OptimizationProposal)
        assert proposal.confidence > 0.75
        assert proposal.evidence_count >= 10


def test_optimizer_apply_empty(temp_db: Database) -> None:
    """Test apply with no proposals."""
    optimizer = Optimizer(temp_db)

    result = optimizer.apply([])

    assert result is False


def test_optimizer_apply_proposals(temp_db: Database) -> None:
    """Test applying optimization proposals."""
    optimizer = Optimizer(temp_db)

    proposals = [
        OptimizationProposal(
            parameter="quality_threshold",
            current_value=3.0,
            proposed_value=3.5,
            confidence=0.85,
            evidence_count=50,
            improvement_pct=16.7,
        )
    ]

    result = optimizer.apply(proposals)

    assert result is True

    # Check baselines were saved
    baselines = optimizer._load_baselines()
    assert baselines["quality_threshold"] == 3.5


def test_optimizer_rollback_no_history(temp_db: Database) -> None:
    """Test rollback with no history."""
    optimizer = Optimizer(temp_db)

    result = optimizer.rollback()

    assert result is False


def test_optimizer_rollback_with_history(temp_db: Database) -> None:
    """Test rollback with existing history."""
    optimizer = Optimizer(temp_db)

    # Apply first proposal
    proposal1 = OptimizationProposal(
        parameter="quality_threshold",
        current_value=3.0,
        proposed_value=3.5,
        confidence=0.85,
        evidence_count=50,
        improvement_pct=16.7,
    )
    optimizer.apply([proposal1])

    # Apply second proposal
    proposal2 = OptimizationProposal(
        parameter="quality_threshold",
        current_value=3.5,
        proposed_value=4.0,
        confidence=0.90,
        evidence_count=60,
        improvement_pct=14.3,
    )
    optimizer.apply([proposal2])

    # Rollback to first version
    result = optimizer.rollback()

    assert result is True

    # Check baselines reverted
    baselines = optimizer._load_baselines()
    assert baselines["quality_threshold"] == 3.5
