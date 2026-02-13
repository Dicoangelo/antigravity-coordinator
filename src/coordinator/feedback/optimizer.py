"""Self-optimization feedback loop.

Analyzes session outcomes to propose parameter optimizations.
Requires 50+ sessions before proposing changes.
Only applies proposals with >75% confidence.

"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from coordinator.storage.database import Database


@dataclass
class OptimizationProposal:
    """Proposal for optimizing a parameter."""

    parameter: str
    current_value: float
    proposed_value: float
    confidence: float
    evidence_count: int
    improvement_pct: float


class Optimizer:
    """Self-optimization engine for coordinator parameters."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.baselines_file = Path.home() / ".coordinator" / "data" / "baselines.json"

    def propose(self) -> list[OptimizationProposal]:
        """Generate optimization proposals based on session outcomes.

        Requires at least 50 sessions before proposing changes.
        Only returns proposals with confidence > 75%.

        Returns:
            List of OptimizationProposal objects

        """
        # Query outcomes from database
        rows = self.db.execute(
            """
            SELECT outcome, quality, complexity, model_efficiency, dq_score
            FROM outcomes
            ORDER BY analyzed_at DESC
            LIMIT 200
            """
        )

        if len(rows) < 50:
            # Not enough data
            return []

        # Calculate optimal thresholds
        proposals: list[OptimizationProposal] = []

        # 1. Quality threshold optimization
        quality_proposal = self._optimize_quality_threshold(rows)
        if quality_proposal and quality_proposal.confidence > 0.75:
            proposals.append(quality_proposal)

        # 2. Complexity threshold optimization
        complexity_proposal = self._optimize_complexity_threshold(rows)
        if complexity_proposal and complexity_proposal.confidence > 0.75:
            proposals.append(complexity_proposal)

        # 3. Model efficiency threshold
        efficiency_proposal = self._optimize_efficiency_threshold(rows)
        if efficiency_proposal and efficiency_proposal.confidence > 0.75:
            proposals.append(efficiency_proposal)

        return proposals

    def apply(self, proposals: list[OptimizationProposal]) -> bool:
        """Apply optimization proposals to baselines.

        Updates baselines file and records lineage in database.

        Args:
            proposals: List of OptimizationProposal to apply

        Returns:
            True if successful, False otherwise

        """
        if not proposals:
            return False

        # Load current baselines
        baselines = self._load_baselines()

        # Apply proposals
        for proposal in proposals:
            baselines[proposal.parameter] = proposal.proposed_value

        # Save updated baselines
        self._save_baselines(baselines)

        # Record lineage in database
        lineage = [
            {
                "parameter": p.parameter,
                "from": p.current_value,
                "to": p.proposed_value,
                "confidence": p.confidence,
                "evidence": p.evidence_count,
            }
            for p in proposals
        ]

        self.db.execute_insert(
            """
            INSERT INTO baselines (version, parameters, evidence_count, confidence, lineage)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                self._next_version(),
                json.dumps(baselines),
                sum(p.evidence_count for p in proposals),
                sum(p.confidence for p in proposals) / len(proposals),
                json.dumps(lineage),
            ),
        )

        return True

    def rollback(self) -> bool:
        """Revert to previous baseline version.

        Returns:
            True if rollback successful, False otherwise

        """
        # Get previous version
        rows = self.db.execute(
            """
            SELECT parameters
            FROM baselines
            ORDER BY id DESC
            LIMIT 2
            """
        )

        if len(rows) < 2:
            # No previous version
            return False

        # Load previous parameters
        prev_params = json.loads(rows[1]["parameters"])

        # Save as current baselines
        self._save_baselines(prev_params)

        return True

    def _optimize_quality_threshold(self, rows: Sequence[Any]) -> OptimizationProposal | None:
        """Optimize quality threshold based on outcomes."""
        # Extract quality scores
        qualities = [float(row["quality"]) for row in rows if row["quality"]]

        if not qualities:
            return None

        # Calculate optimal threshold (median of successful sessions)
        successful = [q for q, row in zip(qualities, rows) if row["outcome"] == "success"]

        if len(successful) < 10:
            return None

        optimal = sum(successful) / len(successful)
        current = self._load_baselines().get("quality_threshold", 3.0)

        improvement = abs(optimal - current) / current if current > 0 else 0.0
        confidence = min(1.0, len(successful) / 50.0)

        return OptimizationProposal(
            parameter="quality_threshold",
            current_value=current,
            proposed_value=optimal,
            confidence=confidence,
            evidence_count=len(successful),
            improvement_pct=improvement * 100,
        )

    def _optimize_complexity_threshold(self, rows: Sequence[Any]) -> OptimizationProposal | None:
        """Optimize complexity threshold for model routing."""
        complexities = [float(row["complexity"]) for row in rows if row["complexity"]]

        if not complexities:
            return None

        # Calculate threshold between low/high complexity
        sorted_c = sorted(complexities)
        median_idx = len(sorted_c) // 2
        optimal = sorted_c[median_idx]

        current = self._load_baselines().get("complexity_threshold", 0.5)

        improvement = abs(optimal - current) / current if current > 0 else 0.0
        confidence = min(1.0, len(complexities) / 50.0)

        return OptimizationProposal(
            parameter="complexity_threshold",
            current_value=current,
            proposed_value=optimal,
            confidence=confidence,
            evidence_count=len(complexities),
            improvement_pct=improvement * 100,
        )

    def _optimize_efficiency_threshold(self, rows: Sequence[Any]) -> OptimizationProposal | None:
        """Optimize model efficiency threshold."""
        efficiencies = [float(row["model_efficiency"]) for row in rows if row["model_efficiency"]]

        if not efficiencies:
            return None

        # Calculate average efficiency of successful sessions
        successful = [e for e, row in zip(efficiencies, rows) if row["outcome"] == "success"]

        if len(successful) < 10:
            return None

        optimal = sum(successful) / len(successful)
        current = self._load_baselines().get("efficiency_threshold", 0.7)

        improvement = abs(optimal - current) / current if current > 0 else 0.0
        confidence = min(1.0, len(successful) / 50.0)

        return OptimizationProposal(
            parameter="efficiency_threshold",
            current_value=current,
            proposed_value=optimal,
            confidence=confidence,
            evidence_count=len(successful),
            improvement_pct=improvement * 100,
        )

    def _load_baselines(self) -> dict[str, float]:
        """Load current baselines from file."""
        if not self.baselines_file.exists():
            return {
                "quality_threshold": 3.0,
                "complexity_threshold": 0.5,
                "efficiency_threshold": 0.7,
            }

        with open(self.baselines_file) as f:
            data: dict[str, float] = json.load(f)
            return data

    def _save_baselines(self, baselines: dict[str, float]) -> None:
        """Save baselines to file."""
        self.baselines_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.baselines_file, "w") as f:
            json.dump(baselines, f, indent=2)

    def _next_version(self) -> str:
        """Get next baseline version string."""
        rows = self.db.execute(
            """
            SELECT version
            FROM baselines
            ORDER BY id DESC
            LIMIT 1
            """
        )

        if not rows:
            return "1.0.0"

        current = rows[0]["version"]
        # Simple increment: 1.0.0 -> 1.0.1
        parts = current.split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)
