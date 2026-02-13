"""Coordination strategies."""

from coordinator.strategies.base import BaseStrategy, StrategyResult
from coordinator.strategies.full import FullStrategy
from coordinator.strategies.implement import ImplementStrategy
from coordinator.strategies.research import ResearchStrategy
from coordinator.strategies.review import ReviewStrategy
from coordinator.strategies.team import TeamStrategy

STRATEGIES: dict[str, type[BaseStrategy]] = {
    "research": ResearchStrategy,
    "implement": ImplementStrategy,
    "review": ReviewStrategy,
    "full": FullStrategy,
    "team": TeamStrategy,
}

__all__ = [
    "BaseStrategy",
    "StrategyResult",
    "ResearchStrategy",
    "ImplementStrategy",
    "ReviewStrategy",
    "FullStrategy",
    "TeamStrategy",
    "STRATEGIES",
]
