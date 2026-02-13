"""Research strategy: spawns 3 parallel explore agents."""

from __future__ import annotations

from coordinator.strategies.base import BaseStrategy, StrategyResult


class ResearchStrategy(BaseStrategy):
    """Parallel research strategy for exploration tasks.

    Spawns 3 parallel explore agents to research different aspects of a topic:
    - Architecture exploration
    - Pattern discovery
    - Dependency analysis

    All agents are read-only, so they can run in parallel without conflicts.

    """

    name = "research"
    description = "3 parallel explore agents for understanding and investigation"

    def execute(self, task: str, options: dict[str, object] | None = None) -> StrategyResult:
        """Execute parallel research strategy.

        Args:
            task: Research task description
            options: Optional parameters (num_agents, timeout, etc.)

        Returns:
            StrategyResult with stub outputs (actual spawning is engine-level)

        """
        opts = options or {}
        num_agents_val = opts.get("num_agents", 3)
        num_agents = int(num_agents_val) if isinstance(num_agents_val, (int, str, float)) else 3

        # Generate research subtasks (agent spawning is engine-level)
        subtasks = self._generate_subtasks(task, num_agents)

        # Return stub result (actual execution happens in engine)
        return StrategyResult(
            session_id="stub",
            strategy=self.name,
            agents_spawned=num_agents,
            status="pending",
            outputs=[f"Research: {st}" for st in subtasks],
            duration_seconds=0.0,
        )

    def _generate_subtasks(self, task: str, num_agents: int) -> list[str]:
        """Generate research subtasks for parallel exploration."""
        angles = [
            ("architecture", "Explore the overall architecture and structure for"),
            ("patterns", "Find similar patterns and implementations for"),
            ("dependencies", "Analyze dependencies and connections for"),
        ]

        return [f"{prompt}: {task}" for _, prompt in angles[:num_agents]]
