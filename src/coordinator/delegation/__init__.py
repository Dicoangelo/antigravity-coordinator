"""
Intelligent Delegation — Multi-Agent Task Decomposition & Trust

Implements the intelligent delegation framework from arXiv:2602.11865.
Provides task taxonomy, decomposition, routing, trust tracking, coordination,
and verification for sovereign multi-agent orchestration.

Core Components:
- models: 11-dimensional TaskProfile, SubTask, Assignment dataclasses
- taxonomy: Task classification (LLM + heuristic fallback)
- decomposer: Contract-first recursive decomposition
- router: Capability-weighted agent selection with fallback chains
- trust_ledger: Bayesian Beta trust scoring with time decay
- four_ds: Anthropic 4Ds gates (delegation/description/discernment/diligence)
- evolution: EMA learning from delegation outcomes
- executor: Subtask execution dispatcher
"""

__version__ = "0.1.0"

from .models import (
    Assignment,
    DelegationEvent,
    SubTask,
    TaskProfile,
    TrustEntry,
    VerificationMethod,
    VerificationResult,
)
from .taxonomy import classify_task, compute_delegation_overhead, compute_risk_score
from .decomposer import decompose_task
from .router import AgentCapability, route_batch, route_subtask
from .four_ds import (
    FourDsGate,
    delegation_gate,
    description_gate,
    discernment_gate,
    diligence_gate,
)
from .trust_ledger import AgentTrustScore, TrustLedger
from .evolution import EvolutionEngine
from .executor import ExecutionResult, SubtaskExecutor

__all__ = [
    # Models
    "Assignment",
    "DelegationEvent",
    "SubTask",
    "TaskProfile",
    "TrustEntry",
    "VerificationMethod",
    "VerificationResult",
    # Taxonomy
    "classify_task",
    "compute_delegation_overhead",
    "compute_risk_score",
    # Decomposer
    "decompose_task",
    # Router
    "AgentCapability",
    "route_batch",
    "route_subtask",
    # 4Ds
    "FourDsGate",
    "delegation_gate",
    "description_gate",
    "discernment_gate",
    "diligence_gate",
    # Trust
    "AgentTrustScore",
    "TrustLedger",
    # Evolution
    "EvolutionEngine",
    # Executor
    "ExecutionResult",
    "SubtaskExecutor",
]
