"""Tests for coordination strategies."""

from __future__ import annotations

import pytest

from coordinator.strategies import (
    STRATEGIES,
    FullStrategy,
    ImplementStrategy,
    ResearchStrategy,
    ReviewStrategy,
    StrategyResult,
    TeamStrategy,
)


def test_strategy_registry() -> None:
    """Test that all strategies are registered."""
    assert "research" in STRATEGIES
    assert "implement" in STRATEGIES
    assert "review" in STRATEGIES
    assert "full" in STRATEGIES
    assert "team" in STRATEGIES

    assert STRATEGIES["research"] == ResearchStrategy
    assert STRATEGIES["implement"] == ImplementStrategy
    assert STRATEGIES["review"] == ReviewStrategy
    assert STRATEGIES["full"] == FullStrategy
    assert STRATEGIES["team"] == TeamStrategy


def test_research_strategy() -> None:
    """Test ResearchStrategy execution."""
    strategy = ResearchStrategy()

    assert strategy.name == "research"
    assert strategy.description

    result = strategy.execute("Explore the codebase architecture")

    assert isinstance(result, StrategyResult)
    assert result.strategy == "research"
    assert result.agents_spawned == 3
    assert result.status == "pending"
    assert len(result.outputs) == 3


def test_research_strategy_custom_agents() -> None:
    """Test ResearchStrategy with custom agent count."""
    strategy = ResearchStrategy()

    result = strategy.execute(
        "Research database patterns", options={"num_agents": 2}
    )

    assert result.agents_spawned == 2
    assert len(result.outputs) == 2


def test_implement_strategy() -> None:
    """Test ImplementStrategy execution."""
    strategy = ImplementStrategy()

    assert strategy.name == "implement"
    assert strategy.description

    result = strategy.execute("Implement new feature")

    assert isinstance(result, StrategyResult)
    assert result.strategy == "implement"
    assert result.agents_spawned == 1
    assert result.status == "pending"


def test_implement_strategy_with_files() -> None:
    """Test ImplementStrategy with file assignments."""
    strategy = ImplementStrategy()

    result = strategy.execute(
        "Update database schema",
        options={"num_agents": 2, "files": [["db.py"], ["schema.sql"]]},
    )

    assert result.agents_spawned == 2


def test_review_strategy() -> None:
    """Test ReviewStrategy execution."""
    strategy = ReviewStrategy()

    assert strategy.name == "review"
    assert strategy.description

    result = strategy.execute("Implement auth system")

    assert isinstance(result, StrategyResult)
    assert result.strategy == "review"
    assert result.agents_spawned == 2  # builder + reviewer
    assert result.status == "pending"
    assert len(result.outputs) == 2


def test_review_strategy_custom_models() -> None:
    """Test ReviewStrategy with custom models."""
    strategy = ReviewStrategy()

    result = strategy.execute(
        "Add new API endpoint",
        options={"builder_model": "opus", "reviewer_model": "sonnet"},
    )

    assert result.agents_spawned == 2
    assert "opus" in result.outputs[0]
    assert "sonnet" in result.outputs[1]


def test_full_strategy() -> None:
    """Test FullStrategy execution."""
    strategy = FullStrategy()

    assert strategy.name == "full"
    assert strategy.description

    result = strategy.execute("Build new module")

    assert isinstance(result, StrategyResult)
    assert result.strategy == "full"
    assert result.agents_spawned == 6  # 3 research + 1 impl + 2 review
    assert result.status == "pending"
    assert len(result.outputs) == 3  # 3 phases


def test_full_strategy_custom_phases() -> None:
    """Test FullStrategy with custom phase configurations."""
    strategy = FullStrategy()

    result = strategy.execute(
        "Complex refactoring",
        options={"research_agents": 2, "impl_agents": 3, "review_agents": 1},
    )

    assert result.agents_spawned == 6  # 2 + 3 + 1


def test_team_strategy() -> None:
    """Test TeamStrategy execution."""
    strategy = TeamStrategy()

    assert strategy.name == "team"
    assert strategy.description

    result = strategy.execute("Complex multi-part task")

    assert isinstance(result, StrategyResult)
    assert result.strategy == "team"
    assert result.agents_spawned == 3
    assert result.status == "pending"


def test_team_strategy_custom_coordination() -> None:
    """Test TeamStrategy with custom coordination mode."""
    strategy = TeamStrategy()

    result = strategy.execute(
        "Distributed system design",
        options={"num_agents": 5, "coordination_mode": "hierarchical"},
    )

    assert result.agents_spawned == 5
    assert "hierarchical" in result.outputs[0]


def test_strategy_result_defaults() -> None:
    """Test StrategyResult default values."""
    result = StrategyResult(
        session_id="test-123", strategy="research", agents_spawned=3
    )

    assert result.status == "completed"
    assert result.outputs == []
    assert result.duration_seconds == 0.0


def test_strategy_result_with_outputs() -> None:
    """Test StrategyResult with custom values."""
    result = StrategyResult(
        session_id="test-456",
        strategy="implement",
        agents_spawned=2,
        status="running",
        outputs=["Agent 1 output", "Agent 2 output"],
        duration_seconds=123.45,
    )

    assert result.status == "running"
    assert len(result.outputs) == 2
    assert result.duration_seconds == 123.45
