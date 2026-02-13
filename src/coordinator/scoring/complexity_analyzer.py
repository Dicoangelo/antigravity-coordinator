#!/usr/bin/env python3
"""Complexity Analyzer - Astraea-inspired query complexity estimation.

Based on: "Astraea: A State-Aware Scheduling Engine for LLM-Powered Agents"
arXiv: https://arxiv.org/abs/2512.14142

Estimates query complexity to inform model routing decisions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

# ═══════════════════════════════════════════════════════════════════════════
# COMPLEXITY SIGNALS
# ═══════════════════════════════════════════════════════════════════════════

SIGNALS: Final[dict[str, list[str]]] = {
    # Semantic keywords that indicate complexity
    "code": [
        "function",
        "class",
        "async",
        "import",
        "export",
        "const",
        "let",
        "var",
        "interface",
        "type",
        "enum",
        "module",
        "require",
        "def ",
        "return",
    ],
    "architecture": [
        "design",
        "architecture",
        "system",
        "refactor",
        "restructure",
        "pattern",
        "microservice",
        "distributed",
        "scalable",
        "optimize",
    ],
    "debug": [
        "error",
        "fix",
        "bug",
        "debug",
        "why",
        "not working",
        "broken",
        "crash",
        "exception",
        "failed",
        "issue",
        "problem",
    ],
    "multiFile": [
        "across",
        "all files",
        "every",
        "multiple",
        "entire codebase",
        "project-wide",
        "refactor all",
        "update all",
    ],
    "analysis": [
        "analyze",
        "review",
        "audit",
        "compare",
        "evaluate",
        "assess",
        "investigate",
        "research",
        "study",
        "understand",
    ],
    "creation": [
        "create",
        "build",
        "implement",
        "develop",
        "write",
        "generate",
        "make",
        "add",
        "new feature",
        "from scratch",
    ],
    "simple": [
        "what is",
        "how to",
        "explain",
        "show me",
        "list",
        "print",
        "hello",
        "thanks",
        "yes",
        "no",
        "ok",
    ],
}

# Complexity weights for each signal category
WEIGHTS: Final[dict[str, float]] = {
    "code": 0.15,
    "architecture": 0.25,
    "debug": 0.10,
    "multiFile": 0.20,
    "analysis": 0.15,
    "creation": 0.10,
    "simple": -0.15,  # Negative weight reduces complexity
}

# Token-based complexity thresholds (from Astraea paper)
TOKEN_THRESHOLDS: Final[dict[str, dict[str, float]]] = {
    "simple": {"max": 20, "score": 0.10},
    "moderate": {"max": 100, "score": 0.30},
    "complex": {"max": 500, "score": 0.60},
    "expert": {"max": float("inf"), "score": 0.90},
}


# ═══════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class SignalScore:
    """Score for a single signal category."""

    count: int
    score: float


@dataclass(frozen=True)
class ComplexityResult:
    """Result of complexity estimation."""

    score: float
    tokens: int
    signals: dict[str, SignalScore]
    model: str
    reasoning: str


# ═══════════════════════════════════════════════════════════════════════════
# ANALYSIS FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def tokenize(text: str) -> list[str]:
    """Simple tokenizer - splits on whitespace and punctuation."""
    # Remove non-word characters except spaces
    normalized = re.sub(r"[^\w\s]", " ", text.lower())
    # Split on whitespace and filter empty strings
    return [t for t in normalized.split() if t]


def estimate_tokens(text: str) -> int:
    """Estimate tokens (rough approximation: ~4 chars per token)."""
    return max(1, len(text) // 4)


def has_signals(query: str, category: str) -> bool:
    """Check if query contains keywords from a signal category."""
    lower_query = query.lower()
    return any(keyword in lower_query for keyword in SIGNALS[category])


def count_signals(query: str, category: str) -> int:
    """Count matching signals for a category."""
    lower_query = query.lower()
    return sum(1 for keyword in SIGNALS[category] if keyword in lower_query)


def requires_project_context(query: str) -> bool:
    """Detect if query requires project context."""
    patterns = [
        r"\b(this|our|my|the)\s+\w+\s+(file|code|project|app|component)",
        r"\bin\s+(this|the)\s+(codebase|repo|project)",
        r"\bcurrent\s+(file|directory|project)",
    ]
    return any(re.search(pattern, query, re.IGNORECASE) for pattern in patterns)


def is_conversational(query: str) -> bool:
    """Detect if query is conversational/simple."""
    patterns = [
        r"^(hi|hello|hey|thanks|thank you|ok|okay|yes|no|sure)",
        r"^what (is|are) \w+\??$",
        r"^(how|can|could) (do|can) (i|you)",
    ]
    return any(re.search(pattern, query, re.IGNORECASE) for pattern in patterns) and len(query) < 50


# ═══════════════════════════════════════════════════════════════════════════
# MAIN COMPLEXITY ESTIMATION
# ═══════════════════════════════════════════════════════════════════════════


def estimate_complexity(query: str) -> ComplexityResult:
    """Estimate complexity of a query.

    Returns ComplexityResult with:
        - score: 0-1 complexity score
        - tokens: estimated token count
        - signals: detected signal categories with scores
        - model: recommended model (haiku/sonnet/opus)
        - reasoning: human-readable explanation
    """
    tokens = estimate_tokens(query)
    reasoning_parts: list[str] = []

    # Start with token-based score
    score = 0.0

    # Token length scoring
    if tokens <= TOKEN_THRESHOLDS["simple"]["max"]:
        score += TOKEN_THRESHOLDS["simple"]["score"]
        reasoning_parts.append(f"Short query ({tokens} tokens)")
    elif tokens <= TOKEN_THRESHOLDS["moderate"]["max"]:
        score += TOKEN_THRESHOLDS["moderate"]["score"]
        reasoning_parts.append(f"Medium query ({tokens} tokens)")
    elif tokens <= TOKEN_THRESHOLDS["complex"]["max"]:
        score += TOKEN_THRESHOLDS["complex"]["score"]
        reasoning_parts.append(f"Long query ({tokens} tokens)")
    else:
        score += TOKEN_THRESHOLDS["expert"]["score"]
        reasoning_parts.append(f"Very long query ({tokens} tokens)")

    # Signal-based scoring
    signal_scores: dict[str, SignalScore] = {}
    for category, weight in WEIGHTS.items():
        if has_signals(query, category):
            count = count_signals(query, category)
            # Cap at 3 matches per category
            category_score = weight * min(count, 3)
            signal_scores[category] = SignalScore(count=count, score=category_score)
            score += category_score

            if weight > 0:
                reasoning_parts.append(f"{category}: {count} signal(s)")

    # Context requirements
    if requires_project_context(query):
        score += 0.15
        reasoning_parts.append("Requires project context")

    # Conversational reduction
    if is_conversational(query):
        score -= 0.20
        reasoning_parts.append("Conversational/simple")

    # Clamp to 0-1
    score = max(0.0, min(1.0, score))

    # Determine recommended model
    if score < 0.25:
        model = "haiku"
    elif score < 0.60:
        model = "sonnet"
    else:
        model = "opus"

    return ComplexityResult(
        score=round(score, 3),
        tokens=tokens,
        signals=signal_scores,
        model=model,
        reasoning="; ".join(reasoning_parts),
    )
