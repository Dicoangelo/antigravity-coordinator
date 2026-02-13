"""Tests for DQ scoring and complexity analysis."""

from __future__ import annotations

import pytest

from coordinator.scoring import (
    ComplexityResult,
    DQScore,
    ScoringResult,
    calculate_dq,
    estimate_complexity,
    score,
)
from coordinator.scoring.dq_scorer import (
    ModelName,
    assess_correctness,
    assess_specificity,
    assess_validity,
    load_baselines,
)


# ═══════════════════════════════════════════════════════════════════════════
# COMPLEXITY ESTIMATION TESTS
# ═══════════════════════════════════════════════════════════════════════════


def test_estimate_complexity_simple_query() -> None:
    """Test complexity estimation for simple query."""
    result = estimate_complexity("hello")

    assert isinstance(result, ComplexityResult)
    assert 0.0 <= result.score <= 1.0
    assert result.tokens > 0
    assert result.model in ["haiku", "sonnet", "opus"]
    assert len(result.reasoning) > 0

    # Simple query should have low complexity
    assert result.score < 0.3, f"Expected low complexity, got {result.score}"
    assert result.model == "haiku", f"Expected haiku for simple query, got {result.model}"


def test_estimate_complexity_architecture_query() -> None:
    """Test complexity estimation for architecture query."""
    result = estimate_complexity("Design a distributed caching system")

    assert isinstance(result, ComplexityResult)
    assert 0.0 <= result.score <= 1.0

    # Architecture query should have high complexity
    assert result.score >= 0.6, f"Expected high complexity, got {result.score}"
    assert result.model == "opus", f"Expected opus for architecture query, got {result.model}"

    # Should detect architecture signals
    assert "architecture" in result.signals or "system" in result.reasoning.lower()


def test_estimate_complexity_debug_query() -> None:
    """Test complexity estimation for debug/simple query."""
    result = estimate_complexity("Fix the typo in README")

    assert isinstance(result, ComplexityResult)
    assert 0.0 <= result.score <= 1.0

    # Debug query should have low to moderate complexity
    assert result.score < 0.5, f"Expected low/moderate complexity, got {result.score}"
    assert result.model in [
        "haiku",
        "sonnet",
    ], f"Expected haiku/sonnet for debug query, got {result.model}"


def test_estimate_complexity_moderate_query() -> None:
    """Test complexity estimation for moderate query."""
    result = estimate_complexity(
        "Refactor authentication module to use dependency injection"
    )

    assert isinstance(result, ComplexityResult)
    assert 0.0 <= result.score <= 1.0

    # Moderate refactoring should be sonnet territory
    assert 0.2 <= result.score <= 0.7, f"Expected moderate complexity, got {result.score}"
    assert result.model == "sonnet", f"Expected sonnet for moderate query, got {result.model}"


def test_estimate_complexity_complex_query() -> None:
    """Test complexity estimation for complex query."""
    result = estimate_complexity(
        "Architect a microservices system for real-time data processing at scale"
    )

    assert isinstance(result, ComplexityResult)
    assert 0.0 <= result.score <= 1.0

    # Complex architecture should be high complexity
    assert result.score >= 0.5, f"Expected high complexity, got {result.score}"
    assert result.model in [
        "sonnet",
        "opus",
    ], f"Expected sonnet/opus for complex query, got {result.model}"


# ═══════════════════════════════════════════════════════════════════════════
# DQ SCORING TESTS
# ═══════════════════════════════════════════════════════════════════════════


def test_dq_components_in_range() -> None:
    """Test that DQ components are in valid 0-1 range."""
    baselines = load_baselines()

    queries = [
        ("hello", 0.1, "haiku"),
        ("Design a system", 0.8, "opus"),
        ("Fix bug in code", 0.3, "sonnet"),
    ]

    for query, complexity, model in queries:
        dq = calculate_dq(query, complexity, model, baselines)  # type: ignore[arg-type]

        assert isinstance(dq, DQScore)
        assert 0.0 <= dq.score <= 1.0, f"DQ score out of range: {dq.score}"
        assert 0.0 <= dq.components.validity <= 1.0
        assert 0.0 <= dq.components.specificity <= 1.0
        assert 0.0 <= dq.components.correctness <= 1.0


def test_complexity_in_range() -> None:
    """Test that complexity scores are in valid 0-1 range."""
    queries = [
        "hello",
        "what is python",
        "implement a binary search tree",
        "design a distributed system for real-time analytics",
        "fix typo",
        "refactor authentication to use OAuth2",
    ]

    for query in queries:
        result = estimate_complexity(query)
        assert 0.0 <= result.score <= 1.0, f"Complexity out of range: {result.score}"


def test_assess_validity() -> None:
    """Test validity assessment function."""
    baselines = load_baselines()

    # Good match: low complexity with haiku
    validity = assess_validity(0.1, "haiku", baselines)
    assert validity >= 0.8, "Haiku should be valid for low complexity"

    # Over-provisioning: low complexity with opus
    validity = assess_validity(0.1, "opus", baselines)
    assert validity < 0.8, "Opus should have lower validity for simple tasks"

    # Under-provisioning: high complexity with haiku
    validity = assess_validity(0.9, "haiku", baselines)
    assert validity < 0.5, "Haiku should have low validity for complex tasks"


def test_assess_specificity() -> None:
    """Test specificity assessment function."""
    # Ideal match: moderate complexity with sonnet
    specificity = assess_specificity("test query", 0.4, "sonnet")
    assert specificity >= 0.9, "Sonnet should be highly specific for moderate complexity"

    # Adjacent model
    specificity = assess_specificity("test query", 0.4, "haiku")
    assert 0.5 <= specificity < 0.9, "Adjacent model should have moderate specificity"

    # Wrong model
    specificity = assess_specificity("test query", 0.1, "opus")
    assert specificity < 0.7, "Wrong model should have lower specificity"


def test_assess_correctness_neutral() -> None:
    """Test correctness returns neutral score without history."""
    correctness = assess_correctness("test query", "sonnet", None)
    assert correctness == 0.5, "Should return neutral score without history"


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════


def test_score_simple_query() -> None:
    """Test scoring simple query returns haiku."""
    result = score("hello")

    assert isinstance(result, ScoringResult)
    assert result.model == "haiku"
    assert result.complexity < 0.3
    assert 0.0 <= result.dq.score <= 1.0
    assert result.thinking_effort is None  # No thinking tiers for haiku
    assert result.cost_estimate > 0


def test_score_architecture_query() -> None:
    """Test scoring architecture query returns opus."""
    result = score("Design a distributed caching system")

    assert isinstance(result, ScoringResult)
    assert result.model == "opus"
    assert result.complexity >= 0.6
    assert 0.0 <= result.dq.score <= 1.0
    assert result.thinking_effort in ["low", "medium", "high", "max"]
    assert result.cost_estimate > 0


def test_score_debug_query() -> None:
    """Test scoring debug query returns haiku."""
    result = score("Fix the typo in README")

    assert isinstance(result, ScoringResult)
    assert result.model == "haiku"
    assert result.complexity < 0.5
    assert 0.0 <= result.dq.score <= 1.0
    assert result.thinking_effort is None
    assert result.cost_estimate > 0


def test_score_moderate_query() -> None:
    """Test scoring moderate query returns sonnet."""
    result = score("Refactor authentication module to use dependency injection")

    assert isinstance(result, ScoringResult)
    assert result.model == "sonnet"
    assert 0.2 <= result.complexity <= 0.7
    assert 0.0 <= result.dq.score <= 1.0
    assert result.thinking_effort is None  # No thinking tiers for sonnet
    assert result.cost_estimate > 0


def test_score_complex_query() -> None:
    """Test scoring complex query returns sonnet or opus."""
    result = score("Architect a microservices system for real-time data processing at scale")

    assert isinstance(result, ScoringResult)
    assert result.model in ["sonnet", "opus"]
    assert result.complexity >= 0.5
    assert 0.0 <= result.dq.score <= 1.0
    assert result.cost_estimate > 0


def test_score_with_baselines() -> None:
    """Test scoring with explicit baselines path."""
    from pathlib import Path

    baselines_path = Path(__file__).parent.parent / "src/coordinator/scoring/default_baselines.json"

    result = score("hello", baselines_path)

    assert isinstance(result, ScoringResult)
    assert result.baseline_version == "1.1.0"
    assert result.model == "haiku"


def test_score_result_structure() -> None:
    """Test that ScoringResult has all expected fields."""
    result = score("test query")

    assert hasattr(result, "query")
    assert hasattr(result, "complexity")
    assert hasattr(result, "model")
    assert hasattr(result, "thinking_effort")
    assert hasattr(result, "dq")
    assert hasattr(result, "reasoning")
    assert hasattr(result, "cost_estimate")
    assert hasattr(result, "baseline_version")

    # Check DQ structure
    assert hasattr(result.dq, "score")
    assert hasattr(result.dq, "components")
    assert hasattr(result.dq, "actionable")
    assert hasattr(result.dq.components, "validity")
    assert hasattr(result.dq.components, "specificity")
    assert hasattr(result.dq.components, "correctness")


# ═══════════════════════════════════════════════════════════════════════════
# EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════


def test_empty_query() -> None:
    """Test handling of empty query."""
    result = score("")

    assert isinstance(result, ScoringResult)
    assert result.model == "haiku"  # Should default to simplest model
    assert result.complexity >= 0.0


def test_very_long_query() -> None:
    """Test handling of very long query."""
    long_query = " ".join(["word"] * 1000)
    result = score(long_query)

    assert isinstance(result, ScoringResult)
    assert result.complexity > 0.5  # Long queries should be more complex


def test_special_characters() -> None:
    """Test handling of special characters in query."""
    result = score("Fix bug: ValueError!!! @#$%^&*()")

    assert isinstance(result, ScoringResult)
    assert 0.0 <= result.complexity <= 1.0
    assert result.model in ["haiku", "sonnet", "opus"]
