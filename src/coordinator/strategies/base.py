"""Base strategy class and result types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class StrategyResult:
    """Result from executing a coordination strategy."""

    session_id: str
    strategy: str
    agents_spawned: int
    status: str = "completed"
    outputs: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


class BaseStrategy(ABC):
    """Base class for coordination strategies."""

    name: str
    description: str

    @abstractmethod
    def execute(self, task: str, options: dict[str, object] | None = None) -> StrategyResult:
        """Execute the strategy for a given task.

        Args:
            task: The task description
            options: Optional strategy-specific parameters

        Returns:
            StrategyResult with execution details

        """
        ...
