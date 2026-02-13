#!/usr/bin/env python3
"""Decision Quality (DQ) Scorer - ACE Framework Implementation.

Based on: OS-App Adaptive Convergence Engine (ACE) DQ Framework
Measures: validity (0.35) + specificity (0.25) + correctness (0.40)

Scores routing decisions and learns from history.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from .complexity_analyzer import estimate_complexity

# ═══════════════════════════════════════════════════════════════════════════
# TYPE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════

ModelName = Literal["haiku", "sonnet", "opus"]
ThinkingTier = Literal["low", "medium", "high", "max"]


# ═══════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class DQWeights:
    """Weights for DQ components."""

    validity: float
    specificity: float
    correctness: float


@dataclass(frozen=True)
class DQComponents:
    """Individual DQ component scores."""

    validity: float
    specificity: float
    correctness: float


@dataclass(frozen=True)
class DQScore:
    """Complete DQ scoring result."""

    score: float
    components: DQComponents
    actionable: bool


@dataclass(frozen=True)
class ModelCapabilities:
    """Capabilities and constraints of a model."""

    strengths: list[str]
    weaknesses: list[str]
    max_complexity: float
    cost_per_mtok: dict[str, float]


@dataclass(frozen=True)
class ThinkingTierConfig:
    """Configuration for Opus 4.6 thinking tier."""

    complexity_range: tuple[float, float]
    use_cases: list[str]


@dataclass(frozen=True)
class Baselines:
    """Loaded baseline configuration."""

    version: str
    dq_weights: DQWeights
    dq_threshold: float
    complexity_thresholds: dict[str, Any]
    model_capabilities: dict[ModelName, ModelCapabilities]
    opus_thinking_tiers: dict[ThinkingTier, ThinkingTierConfig]


@dataclass(frozen=True)
class ScoringResult:
    """Complete scoring result for a query."""

    query: str
    complexity: float
    model: ModelName
    thinking_effort: ThinkingTier | None
    dq: DQScore
    reasoning: str
    cost_estimate: float
    baseline_version: str


# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

# Fallback baselines (if no file provided)
DEFAULT_DQ_WEIGHTS: Final[DQWeights] = DQWeights(validity=0.35, specificity=0.25, correctness=0.40)

DEFAULT_DQ_THRESHOLD: Final[float] = 0.5

DEFAULT_MODEL_CAPABILITIES: Final[dict[ModelName, ModelCapabilities]] = {
    "haiku": ModelCapabilities(
        strengths=["quick answers", "simple tasks", "formatting", "short responses"],
        weaknesses=["complex reasoning", "long context", "code generation", "architecture"],
        max_complexity=0.20,
        cost_per_mtok={"input": 0.80, "output": 4.0},
    ),
    "sonnet": ModelCapabilities(
        strengths=["code generation", "analysis", "moderate reasoning", "balanced tasks"],
        weaknesses=["expert-level problems", "novel architecture", "research synthesis"],
        max_complexity=0.70,
        cost_per_mtok={"input": 3.0, "output": 15.0},
    ),
    "opus": ModelCapabilities(
        strengths=[
            "complex reasoning",
            "novel problems",
            "architecture",
            "research",
            "expert tasks",
        ],
        weaknesses=["cost", "latency for simple tasks"],
        max_complexity=1.0,
        cost_per_mtok={"input": 5.0, "output": 25.0},
    ),
}

DEFAULT_OPUS_THINKING_TIERS: Final[dict[ThinkingTier, ThinkingTierConfig]] = {
    "low": ThinkingTierConfig(
        complexity_range=(0.60, 0.72), use_cases=["quick architecture", "simple review"]
    ),
    "medium": ThinkingTierConfig(
        complexity_range=(0.72, 0.85), use_cases=["multi-file refactor", "debugging"]
    ),
    "high": ThinkingTierConfig(
        complexity_range=(0.85, 0.95), use_cases=["complex algorithms", "system design"]
    ),
    "max": ThinkingTierConfig(
        complexity_range=(0.95, 1.00), use_cases=["research synthesis", "frontier problems"]
    ),
}

# Adaptive thresholds for model selection
ADAPTIVE_THRESHOLDS: Final[dict[str, dict[str, Any]]] = {
    "simple": {"complexity": (0.0, 0.25), "model": "haiku"},
    "moderate": {"complexity": (0.25, 0.50), "model": "sonnet"},
    "complex": {"complexity": (0.50, 0.75), "model": "sonnet"},
    "expert": {"complexity": (0.75, 1.0), "model": "opus"},
}


# ═══════════════════════════════════════════════════════════════════════════
# BASELINES LOADING
# ═══════════════════════════════════════════════════════════════════════════


def load_baselines(baselines_path: Path | None = None) -> Baselines:
    """Load baseline configuration from file or use defaults.

    Args:
        baselines_path: Path to baselines.json file. If None, uses defaults.

    Returns:
        Baselines configuration object.
    """
    if baselines_path is None or not baselines_path.exists():
        return Baselines(
            version="hardcoded",
            dq_weights=DEFAULT_DQ_WEIGHTS,
            dq_threshold=DEFAULT_DQ_THRESHOLD,
            complexity_thresholds={},
            model_capabilities=DEFAULT_MODEL_CAPABILITIES,
            opus_thinking_tiers=DEFAULT_OPUS_THINKING_TIERS,
        )

    try:
        with baselines_path.open("r") as f:
            data = json.load(f)

        # Parse DQ weights
        dq_weights_data = data.get("dq_weights", {})
        dq_weights = DQWeights(
            validity=dq_weights_data.get("validity", DEFAULT_DQ_WEIGHTS.validity),
            specificity=dq_weights_data.get("specificity", DEFAULT_DQ_WEIGHTS.specificity),
            correctness=dq_weights_data.get("correctness", DEFAULT_DQ_WEIGHTS.correctness),
        )

        # Parse model capabilities
        model_caps: dict[ModelName, ModelCapabilities] = {}
        cost_data = data.get("cost_per_mtok", {})
        complexity_thresholds = data.get("complexity_thresholds", {})

        model_names: list[ModelName] = ["haiku", "sonnet", "opus"]
        for model_name in model_names:
            threshold_data = complexity_thresholds.get(model_name, {})
            max_complexity = (
                threshold_data.get("range", [0, 0])[1]
                if threshold_data
                else DEFAULT_MODEL_CAPABILITIES[model_name].max_complexity
            )

            cost = cost_data.get(model_name, {})
            model_caps[model_name] = ModelCapabilities(
                strengths=DEFAULT_MODEL_CAPABILITIES[model_name].strengths,
                weaknesses=DEFAULT_MODEL_CAPABILITIES[model_name].weaknesses,
                max_complexity=max_complexity,
                cost_per_mtok={
                    "input": cost.get("input", 0.0),
                    "output": cost.get("output", 0.0),
                },
            )

        # Parse Opus thinking tiers
        thinking_tiers: dict[ThinkingTier, ThinkingTierConfig] = {}
        opus_data = complexity_thresholds.get("opus", {})
        tiers_data = opus_data.get("thinking_tiers", {})

        tier_names: list[ThinkingTier] = ["low", "medium", "high", "max"]
        for tier_name in tier_names:
            tier_data = tiers_data.get(tier_name, {})
            if tier_data:
                comp_range = tier_data.get("complexity_range", [0.0, 1.0])
                thinking_tiers[tier_name] = ThinkingTierConfig(
                    complexity_range=(comp_range[0], comp_range[1]),
                    use_cases=tier_data.get("use_cases", []),
                )
            else:
                thinking_tiers[tier_name] = DEFAULT_OPUS_THINKING_TIERS[tier_name]

        return Baselines(
            version=data.get("version", "unknown"),
            dq_weights=dq_weights,
            dq_threshold=data.get("dq_thresholds", {}).get("actionable", DEFAULT_DQ_THRESHOLD),
            complexity_thresholds=complexity_thresholds,
            model_capabilities=model_caps,
            opus_thinking_tiers=thinking_tiers,
        )
    except Exception:
        # Fall back to defaults on any error
        return Baselines(
            version="hardcoded",
            dq_weights=DEFAULT_DQ_WEIGHTS,
            dq_threshold=DEFAULT_DQ_THRESHOLD,
            complexity_thresholds={},
            model_capabilities=DEFAULT_MODEL_CAPABILITIES,
            opus_thinking_tiers=DEFAULT_OPUS_THINKING_TIERS,
        )


# ═══════════════════════════════════════════════════════════════════════════
# DQ SCORING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def assess_validity(complexity: float, model: ModelName, baselines: Baselines) -> float:
    """Assess validity: Does the model selection make logical sense?

    Args:
        complexity: Complexity score (0-1)
        model: Selected model
        baselines: Baseline configuration

    Returns:
        Validity score (0-1)
    """
    model_caps = baselines.model_capabilities[model]

    # Perfect validity: complexity within model's range
    if complexity <= model_caps.max_complexity:
        # Penalize over-provisioning (using opus for simple tasks)
        over_provision = model_caps.max_complexity - complexity
        if model == "opus" and complexity < 0.5:
            return 0.6  # Wasteful but valid
        if model == "sonnet" and complexity < 0.2:
            return 0.7  # Slightly wasteful
        return 1.0 - (over_provision * 0.2)  # Small penalty for over-provisioning

    # Under-provisioning is worse
    under_provision = complexity - model_caps.max_complexity
    return max(0.0, 1.0 - (under_provision * 2))  # Heavy penalty


def assess_specificity(query: str, complexity: float, model: ModelName) -> float:
    """Assess specificity: How precise is the model selection?

    Args:
        query: Query string (unused, for API compatibility)
        complexity: Complexity score (0-1)
        model: Selected model

    Returns:
        Specificity score (0-1)
    """
    # Check if model matches the ideal for this complexity
    ideal_model: ModelName = "opus"
    for config in ADAPTIVE_THRESHOLDS.values():
        comp_range = config["complexity"]
        if comp_range[0] <= complexity < comp_range[1]:
            ideal_model = config["model"]
            break

    if model == ideal_model:
        return 1.0

    # Adjacent model is acceptable
    models: list[ModelName] = ["haiku", "sonnet", "opus"]
    ideal_idx = models.index(ideal_model)
    actual_idx = models.index(model)
    distance = abs(ideal_idx - actual_idx)

    return max(0.0, 1.0 - (distance * 0.4))


def assess_correctness(
    query: str, model: ModelName, history: list[dict[str, Any]] | None = None
) -> float:
    """Assess correctness: Historical accuracy for similar queries.

    Args:
        query: Query string
        model: Selected model
        history: Historical routing decisions (unused in standalone mode)

    Returns:
        Correctness score (0-1)
    """
    # In standalone mode without database access, return neutral score
    # This will be overridden by the coordinator when it has access to history
    return 0.5


def calculate_dq(
    query: str,
    complexity: float,
    model: ModelName,
    baselines: Baselines,
    history: list[dict[str, Any]] | None = None,
) -> DQScore:
    """Calculate composite DQ score.

    Args:
        query: Query string
        complexity: Complexity score (0-1)
        model: Selected model
        baselines: Baseline configuration
        history: Historical routing decisions (optional)

    Returns:
        DQScore with overall score and component breakdown
    """
    validity = assess_validity(complexity, model, baselines)
    specificity = assess_specificity(query, complexity, model)
    correctness = assess_correctness(query, model, history)

    weights = baselines.dq_weights
    score = (
        validity * weights.validity
        + specificity * weights.specificity
        + correctness * weights.correctness
    )

    return DQScore(
        score=round(score, 3),
        components=DQComponents(
            validity=round(validity, 3),
            specificity=round(specificity, 3),
            correctness=round(correctness, 3),
        ),
        actionable=score >= baselines.dq_threshold,
    )


# ═══════════════════════════════════════════════════════════════════════════
# OPUS 4.6 THINKING TIERS
# ═══════════════════════════════════════════════════════════════════════════


def get_thinking_effort(
    complexity: float, model: ModelName, baselines: Baselines
) -> ThinkingTier | None:
    """Determine thinking effort level for Opus 4.6.

    Maps complexity score to adaptive thinking effort.

    Args:
        complexity: Complexity score (0-1)
        model: Selected model
        baselines: Baseline configuration

    Returns:
        Thinking tier name or None if not using Opus
    """
    if model != "opus":
        return None

    for tier_name, config in baselines.opus_thinking_tiers.items():
        comp_range = config.complexity_range
        if comp_range[0] <= complexity < comp_range[1]:
            return tier_name

    # Fallback: max complexity gets max thinking
    if complexity >= 0.95:
        return "max"
    return "high"


# ═══════════════════════════════════════════════════════════════════════════
# COST ESTIMATION
# ═══════════════════════════════════════════════════════════════════════════


def estimate_cost(model: ModelName, query_text: str, baselines: Baselines) -> float:
    """Estimate cost for this routing decision.

    Args:
        model: Selected model
        query_text: Query string
        baselines: Baseline configuration

    Returns:
        Estimated cost in dollars
    """
    model_caps = baselines.model_capabilities[model]

    # Rough estimate: query ~100 tokens, response ~500 tokens
    est_input_tokens = max(100, len(query_text) // 4)
    est_output_tokens = 500

    cost = (
        est_input_tokens * model_caps.cost_per_mtok["input"] / 1_000_000
        + est_output_tokens * model_caps.cost_per_mtok["output"] / 1_000_000
    )

    return cost


# ═══════════════════════════════════════════════════════════════════════════
# ROUTING DECISION
# ═══════════════════════════════════════════════════════════════════════════


def score(query: str, baselines_path: Path | None = None) -> ScoringResult:
    """Make a routing decision with DQ scoring.

    This is the main entry point for the scoring module.

    Args:
        query: Query string to score
        baselines_path: Optional path to baselines.json file

    Returns:
        ScoringResult with model selection, DQ scores, and metadata
    """
    baselines = load_baselines(baselines_path)
    complexity_result = estimate_complexity(query)

    # Try each model and pick best DQ
    models: list[ModelName] = ["haiku", "sonnet", "opus"]

    @dataclass
    class Candidate:
        model: ModelName
        dq: DQScore
        complexity: float

    candidates: list[Candidate] = []

    for model in models:
        dq = calculate_dq(query, complexity_result.score, model, baselines)
        candidates.append(Candidate(model=model, dq=dq, complexity=complexity_result.score))

    # Sort by DQ score (highest first), then by cost (lowest first for ties)
    cost_order: dict[ModelName, int] = {"haiku": 0, "sonnet": 1, "opus": 2}
    candidates.sort(key=lambda x: (-x.dq.score, cost_order[x.model]))

    best = candidates[0]
    best_model: ModelName = best.model

    # Determine thinking effort for Opus 4.6
    thinking_effort = get_thinking_effort(complexity_result.score, best_model, baselines)

    # Estimate cost
    cost_est = estimate_cost(best_model, query, baselines)

    return ScoringResult(
        query=query[:200],  # Truncate for storage
        complexity=complexity_result.score,
        model=best_model,
        thinking_effort=thinking_effort,
        dq=best.dq,
        reasoning=complexity_result.reasoning,
        cost_estimate=cost_est,
        baseline_version=baselines.version,
    )
