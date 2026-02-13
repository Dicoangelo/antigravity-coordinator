"""Multi-agent coordination engine."""

from coordinator.engine.conflict import (
    ConflictManager,
    FileLock,
    LockType,
    detect_potential_conflicts,
)
from coordinator.engine.distribution import (
    TaskAssignment,
    WorkDistributor,
    decompose_task,
)
from coordinator.engine.executor import (
    AgentConfig,
    AgentExecutor,
    AgentResult,
    generate_task_prompt,
    generate_task_tool_config,
)
from coordinator.engine.orchestrator import CoordinationResult, MultiAgentOrchestrator
from coordinator.engine.registry import AgentRecord, AgentRegistry, AgentState

__all__ = [
    "AgentConfig",
    "AgentExecutor",
    "AgentRecord",
    "AgentRegistry",
    "AgentResult",
    "AgentState",
    "ConflictManager",
    "CoordinationResult",
    "FileLock",
    "LockType",
    "MultiAgentOrchestrator",
    "TaskAssignment",
    "WorkDistributor",
    "decompose_task",
    "detect_potential_conflicts",
    "generate_task_prompt",
    "generate_task_tool_config",
]
