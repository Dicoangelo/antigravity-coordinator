"""Entropy-based task allocation inspired by EGSS (Entropic Graph Scheduling System)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TaskInfo:
    """Task information for entropy-based allocation."""

    id: str
    description: str
    complexity: float  # 0-1
    historical_failure_rate: float  # 0-1
    dq_variance: float  # 0-1


@dataclass
class Allocation:
    """Resource allocation result for a task."""

    task_id: str
    model: str  # haiku/sonnet/opus
    timeout_seconds: int
    agent_count: int


class EntropyAllocator:
    """Allocates resources based on task entropy (complexity, failure rate, variance)."""

    # Model costs per second (normalized units)
    MODEL_COSTS = {
        "haiku": 0.1,
        "sonnet": 0.5,
        "opus": 2.0,
    }

    def __init__(self) -> None:
        """Initialize the entropy allocator."""
        pass

    def _calculate_entropy(self, task: TaskInfo) -> float:
        """Calculate entropy score for a task.

        Args:
            task: Task information

        Returns:
            Entropy score (0-1)
        """
        return 0.4 * task.complexity + 0.3 * task.historical_failure_rate + 0.3 * task.dq_variance

    def _allocate_resources(self, entropy: float) -> tuple[str, int, int]:
        """Determine model, timeout, and agent count based on entropy.

        Args:
            entropy: Task entropy score (0-1)

        Returns:
            Tuple of (model, timeout_seconds, agent_count)
        """
        if entropy > 0.7:
            # High entropy: opus model, 2 agents, 600s timeout
            return ("opus", 600, 2)
        elif entropy > 0.3:
            # Medium entropy: sonnet model, 1 agent, 300s timeout
            return ("sonnet", 300, 1)
        else:
            # Low entropy: haiku model, 1 agent, 120s timeout
            return ("haiku", 120, 1)

    def _calculate_cost(self, model: str, timeout: int) -> float:
        """Calculate the cost of a resource allocation.

        Args:
            model: Model name
            timeout: Timeout in seconds

        Returns:
            Cost in normalized units
        """
        return self.MODEL_COSTS[model] * timeout

    def allocate(self, tasks: list[TaskInfo], budget: float) -> list[Allocation]:
        """Allocate resources to tasks within budget constraint.

        Args:
            tasks: List of tasks to allocate
            budget: Total budget available

        Returns:
            List of allocations (may be fewer than tasks if budget exceeded)
        """
        allocations: list[Allocation] = []
        total_cost = 0.0

        # Sort tasks by entropy (highest first) for priority allocation
        tasks_with_entropy = [(task, self._calculate_entropy(task)) for task in tasks]
        tasks_with_entropy.sort(key=lambda x: x[1], reverse=True)

        for task, entropy in tasks_with_entropy:
            model, timeout, agent_count = self._allocate_resources(entropy)
            cost = self._calculate_cost(model, timeout)

            # Check if we can afford this allocation
            if total_cost + cost <= budget:
                allocations.append(
                    Allocation(
                        task_id=task.id,
                        model=model,
                        timeout_seconds=timeout,
                        agent_count=agent_count,
                    )
                )
                total_cost += cost
            else:
                # Try to downgrade to cheaper options
                if model == "opus":
                    # Try sonnet
                    cost = self._calculate_cost("sonnet", 300)
                    if total_cost + cost <= budget:
                        allocations.append(
                            Allocation(
                                task_id=task.id,
                                model="sonnet",
                                timeout_seconds=300,
                                agent_count=1,
                            )
                        )
                        total_cost += cost
                        continue

                if model in ("opus", "sonnet"):
                    # Try haiku
                    cost = self._calculate_cost("haiku", 120)
                    if total_cost + cost <= budget:
                        allocations.append(
                            Allocation(
                                task_id=task.id,
                                model="haiku",
                                timeout_seconds=120,
                                agent_count=1,
                            )
                        )
                        total_cost += cost
                        continue

                # Cannot afford even cheapest option, skip this task
                break

        return allocations
