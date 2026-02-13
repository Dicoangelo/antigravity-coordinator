"""Pattern detection for task classification and strategy suggestion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PatternResult:
    """Result of pattern detection."""

    pattern: str
    confidence: float  # 0-1
    suggested_strategy: str


class PatternDetector:
    """Detects task patterns and suggests execution strategies."""

    # Pattern keywords and their associated strategies
    PATTERNS = {
        "debugging": {
            "keywords": [
                "debug",
                "fix",
                "bug",
                "error",
                "issue",
                "broken",
                "crash",
                "traceback",
            ],
            "strategy": "review",
        },
        "research": {
            "keywords": [
                "research",
                "explore",
                "investigate",
                "understand",
                "analyze",
                "study",
                "survey",
            ],
            "strategy": "research",
        },
        "architecture": {
            "keywords": [
                "architect",
                "design",
                "structure",
                "system",
                "refactor major",
                "redesign",
            ],
            "strategy": "full",
        },
        "refactoring": {
            "keywords": [
                "refactor",
                "rename",
                "extract",
                "reorganize",
                "cleanup",
                "simplify",
            ],
            "strategy": "implement",
        },
        "implementation": {
            "keywords": [
                "implement",
                "build",
                "create",
                "add",
                "feature",
                "develop",
                "new",
            ],
            "strategy": "implement",
        },
        "testing": {
            "keywords": [
                "test",
                "spec",
                "coverage",
                "vitest",
                "jest",
                "pytest",
                "assert",
            ],
            "strategy": "review",
        },
        "documentation": {
            "keywords": [
                "doc",
                "readme",
                "comment",
                "explain",
                "guide",
                "tutorial",
            ],
            "strategy": "research",
        },
        "optimization": {
            "keywords": [
                "optim",
                "performance",
                "speed",
                "efficient",
                "cache",
                "fast",
                "slow",
            ],
            "strategy": "full",
        },
    }

    def __init__(self) -> None:
        """Initialize the pattern detector."""
        pass

    def detect(self, task_description: str) -> PatternResult:
        """Detect pattern in task description.

        Args:
            task_description: Task description text

        Returns:
            Pattern detection result
        """
        task_lower = task_description.lower()

        # Score each pattern
        pattern_scores: dict[str, float] = {}
        total_keywords_matched = 0

        for pattern_name, pattern_data in self.PATTERNS.items():
            keywords = pattern_data["keywords"]
            matches = sum(1 for kw in keywords if kw in task_lower)

            if matches > 0:
                pattern_scores[pattern_name] = matches
                total_keywords_matched += matches

        # No pattern detected
        if not pattern_scores:
            return PatternResult(
                pattern="unknown",
                confidence=0.0,
                suggested_strategy="implement",  # Default strategy
            )

        # Find best pattern
        best_pattern = max(pattern_scores.items(), key=lambda x: x[1])
        pattern_name, max_score = best_pattern

        # Calculate confidence based on how many of the pattern's keywords matched
        pattern_keyword_count = len(self.PATTERNS[pattern_name]["keywords"])
        confidence = min(1.0, max_score / pattern_keyword_count)

        strategy: str = self.PATTERNS[pattern_name]["strategy"]  # type: ignore[assignment]
        return PatternResult(
            pattern=pattern_name,
            confidence=confidence,
            suggested_strategy=strategy,
        )
