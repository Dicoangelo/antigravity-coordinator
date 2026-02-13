"""Full orchestration: Research → Build → Review pipeline."""

from __future__ import annotations

from coordinator.strategies.base import BaseStrategy, StrategyResult


class FullStrategy(BaseStrategy):
    """Full orchestration pipeline strategy.

    Executes a complete 3-phase pipeline:
    1. Research: Parallel exploration (3 agents)
    2. Implementation: Parallel builders with file locking
    3. Review: Parallel reviewers for quality assurance

    """

    name = "full"
    description = "Research → Build → Review pipeline for complete feature development"

    def execute(self, task: str, options: dict[str, object] | None = None) -> StrategyResult:
        """Execute full orchestration pipeline.

        Args:
            task: Task description
            options: Optional parameters (research_agents, impl_agents, etc.)

        Returns:
            StrategyResult with stub outputs (actual spawning is engine-level)

        """
        opts = options or {}
        research_val = opts.get("research_agents", 3)
        impl_val = opts.get("impl_agents", 1)
        review_val = opts.get("review_agents", 2)

        research_agents = int(research_val) if isinstance(research_val, (int, str, float)) else 3
        impl_agents = int(impl_val) if isinstance(impl_val, (int, str, float)) else 1
        review_agents = int(review_val) if isinstance(review_val, (int, str, float)) else 2

        total_agents = research_agents + impl_agents + review_agents

        # Return stub result
        return StrategyResult(
            session_id="stub",
            strategy=self.name,
            agents_spawned=total_agents,
            status="pending",
            outputs=[
                f"Phase 1: Research ({research_agents} agents)",
                f"Phase 2: Implementation ({impl_agents} agents)",
                f"Phase 3: Review ({review_agents} agents)",
            ],
            duration_seconds=0.0,
        )
