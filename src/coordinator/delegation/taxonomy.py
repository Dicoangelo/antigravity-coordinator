"""
Task Taxonomy — 11-Dimensional Task Profiling

Implements the task taxonomy framework from arXiv:2602.11865 Section 3.1.
Provides automated task profiling across 11 dimensions using keyword heuristics,
with optional LLM-based classification when a callable is provided.
"""

import json
import re
from typing import Any, Callable, Dict, Optional

from .models import TaskProfile

# Keyword patterns for heuristic scoring
COMPLEXITY_KEYWORDS: Dict[str, list[str]] = {
    "high": [
        "implement", "design", "architect", "optimize", "refactor",
        "research", "analyze", "synthesize",
    ],
    "medium": ["update", "modify", "integrate", "configure", "debug", "test"],
    "low": ["read", "check", "view", "list", "display", "print", "get", "fetch"],
}

CRITICALITY_KEYWORDS: Dict[str, list[str]] = {
    "high": [
        "security", "authentication", "payment", "data loss", "crash",
        "production", "critical",
    ],
    "medium": ["user experience", "performance", "feature", "important"],
    "low": ["cosmetic", "minor", "optional", "nice to have"],
}

UNCERTAINTY_KEYWORDS: Dict[str, list[str]] = {
    "high": ["explore", "investigate", "research", "unclear", "ambiguous", "unknown"],
    "medium": ["figure out", "decide", "choose", "determine"],
    "low": ["implement", "following spec", "as described", "specified"],
}


def _heuristic_score_dimension(task_description: str, dimension: str) -> float:
    """Score a single dimension using keyword heuristics."""
    desc_lower = task_description.lower()

    if dimension == "complexity":
        for keyword in COMPLEXITY_KEYWORDS["high"]:
            if keyword in desc_lower:
                return 0.7
        for keyword in COMPLEXITY_KEYWORDS["medium"]:
            if keyword in desc_lower:
                return 0.5
        for keyword in COMPLEXITY_KEYWORDS["low"]:
            if keyword in desc_lower:
                return 0.2
        return 0.5

    elif dimension == "criticality":
        for keyword in CRITICALITY_KEYWORDS["high"]:
            if keyword in desc_lower:
                return 0.8
        for keyword in CRITICALITY_KEYWORDS["medium"]:
            if keyword in desc_lower:
                return 0.5
        for keyword in CRITICALITY_KEYWORDS["low"]:
            if keyword in desc_lower:
                return 0.2
        return 0.4

    elif dimension == "uncertainty":
        for keyword in UNCERTAINTY_KEYWORDS["high"]:
            if keyword in desc_lower:
                return 0.8
        for keyword in UNCERTAINTY_KEYWORDS["medium"]:
            if keyword in desc_lower:
                return 0.5
        for keyword in UNCERTAINTY_KEYWORDS["low"]:
            if keyword in desc_lower:
                return 0.2
        return 0.5

    elif dimension == "verifiability":
        if any(kw in desc_lower for kw in ["test", "verify", "check", "validate"]):
            return 0.8
        if any(kw in desc_lower for kw in ["design", "choose", "decide"]):
            return 0.4
        return 0.6

    elif dimension == "reversibility":
        if any(
            kw in desc_lower
            for kw in ["delete", "drop", "remove", "deploy", "publish"]
        ):
            return 0.3
        if any(
            kw in desc_lower
            for kw in ["code", "implement", "refactor", "update"]
        ):
            return 0.8
        return 0.6

    elif dimension == "duration":
        complexity = _heuristic_score_dimension(desc_lower, "complexity")
        return min(1.0, complexity + 0.1)

    elif dimension == "cost":
        if any(kw in desc_lower for kw in ["api", "llm", "model", "compute"]):
            return 0.6
        return 0.3

    elif dimension == "resource_requirements":
        if any(
            kw in desc_lower
            for kw in ["integrate", "connect", "api", "database", "service"]
        ):
            return 0.6
        return 0.4

    elif dimension == "constraints":
        if any(
            kw in desc_lower
            for kw in ["must", "required", "constraint", "limitation"]
        ):
            return 0.6
        return 0.3

    elif dimension == "contextuality":
        if any(
            kw in desc_lower
            for kw in ["existing", "current", "integrate with", "based on"]
        ):
            return 0.7
        return 0.4

    elif dimension == "subjectivity":
        if any(kw in desc_lower for kw in ["design", "ux", "ui", "choose", "aesthetic"]):
            return 0.7
        if any(
            kw in desc_lower
            for kw in ["implement", "algorithm", "optimize", "test"]
        ):
            return 0.3
        return 0.5

    return 0.5


DIMENSIONS = [
    "complexity", "criticality", "uncertainty", "duration", "cost",
    "resource_requirements", "constraints", "verifiability",
    "reversibility", "contextuality", "subjectivity",
]


def _heuristic_classify(
    task_description: str, context: Optional[Dict[str, Any]] = None
) -> TaskProfile:
    """Classify task using keyword heuristics."""
    scores: Dict[str, float] = {}
    for dim in DIMENSIONS:
        scores[dim] = _heuristic_score_dimension(task_description, dim)

    if context:
        if context.get("is_critical"):
            scores["criticality"] = max(scores["criticality"], 0.7)
        if context.get("time_sensitive"):
            scores["duration"] = max(scores["duration"], 0.6)
        if context.get("high_stakes"):
            scores["reversibility"] = min(scores["reversibility"], 0.4)

    return TaskProfile(**scores)


def classify_task(
    description: str,
    context: Optional[Dict[str, Any]] = None,
    llm_classify_fn: Optional[Callable[..., TaskProfile]] = None,
) -> TaskProfile:
    """
    Classify a task across 11 dimensions for intelligent delegation.

    Args:
        description: Task description to classify
        context: Optional context dict with additional info
        llm_classify_fn: Optional callable for LLM-based classification.
            If provided and succeeds, its result is used; otherwise falls
            back to heuristic classification.

    Returns:
        TaskProfile with all dimensions scored
    """
    if not description or not description.strip():
        raise ValueError("Task description cannot be empty")

    if llm_classify_fn is not None:
        try:
            return llm_classify_fn(description, context)
        except Exception:
            pass

    return _heuristic_classify(description, context)


def compute_delegation_overhead(profile: TaskProfile) -> float:
    """
    Compute delegation overhead score.

    Returns [0.0, 1.0] where < 0.2 means don't delegate.
    """
    if profile.complexity < 0.2:
        return 0.1

    overhead = 1.0 - (
        profile.complexity * 0.5 + profile.duration * 0.3 + profile.cost * 0.2
    )
    return max(0.0, min(1.0, overhead))


def compute_risk_score(profile: TaskProfile) -> float:
    """
    Compute risk score: criticality * (1-reversibility) * uncertainty.

    Returns [0.0, 1.0].
    """
    risk = (
        profile.criticality * 0.5
        + (1.0 - profile.reversibility) * 0.3
        + profile.uncertainty * 0.2
    )
    return max(0.0, min(1.0, risk))
