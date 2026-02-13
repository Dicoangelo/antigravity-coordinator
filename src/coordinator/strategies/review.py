"""Review strategy: builder + reviewer in parallel."""

from __future__ import annotations

from coordinator.strategies.base import BaseStrategy, StrategyResult


class ReviewStrategy(BaseStrategy):
    """Review + build strategy with concurrent execution.

    Spawns a builder agent (write mode) and a reviewer agent (read mode) in parallel.
    Builder implements while reviewer analyzes and provides feedback.
    No conflicts since reviewer is read-only.

    """

    name = "review"
    description = "Builder + reviewer concurrent for quality-assured implementation"

    def execute(self, task: str, options: dict[str, object] | None = None) -> StrategyResult:
        """Execute review + build strategy.

        Args:
            task: Task description
            options: Optional parameters (builder_model, reviewer_model, etc.)

        Returns:
            StrategyResult with stub outputs (actual spawning is engine-level)

        """
        opts = options or {}
        builder_model = opts.get("builder_model", "sonnet")
        reviewer_model = opts.get("reviewer_model", "haiku")

        # Return stub result
        return StrategyResult(
            session_id="stub",
            strategy=self.name,
            agents_spawned=2,
            status="pending",
            outputs=[
                f"Builder ({builder_model}): {task}",
                f"Reviewer ({reviewer_model}): Review {task}",
            ],
            duration_seconds=0.0,
        )
