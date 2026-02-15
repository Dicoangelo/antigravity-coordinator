"""
Delegation Data Models

Core dataclasses for intelligent delegation system based on arXiv:2602.11865.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class VerificationMethod(str, Enum):
    """Subtask verification methods."""

    AUTOMATED_TEST = "automated_test"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    HUMAN_REVIEW = "human_review"
    GROUND_TRUTH = "ground_truth"


@dataclass
class TaskProfile:
    """
    11-dimensional task profile from arXiv:2602.11865.

    All dimensions are normalized to [0.0, 1.0] for consistent scoring.
    """

    complexity: float = 0.5
    criticality: float = 0.5
    uncertainty: float = 0.5
    duration: float = 0.5
    cost: float = 0.5
    resource_requirements: float = 0.5
    constraints: float = 0.5
    verifiability: float = 0.5
    reversibility: float = 0.5
    contextuality: float = 0.5
    subjectivity: float = 0.5

    def __post_init__(self) -> None:
        for field_name in [
            "complexity",
            "criticality",
            "uncertainty",
            "duration",
            "cost",
            "resource_requirements",
            "constraints",
            "verifiability",
            "reversibility",
            "contextuality",
            "subjectivity",
        ]:
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must be in [0.0, 1.0], got {value}")


@dataclass
class SubTask:
    """Decomposed subtask ready for delegation."""

    id: str
    description: str
    verification_method: VerificationMethod
    estimated_cost: float
    estimated_duration: float
    parallel_safe: bool
    parent_task_id: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    profile: Optional[TaskProfile] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.estimated_cost <= 1.0:
            raise ValueError(
                f"estimated_cost must be in [0.0, 1.0], got {self.estimated_cost}"
            )
        if not 0.0 <= self.estimated_duration <= 1.0:
            raise ValueError(
                f"estimated_duration must be in [0.0, 1.0], got {self.estimated_duration}"
            )


@dataclass
class Assignment:
    """Agent assignment for a subtask."""

    subtask_id: str
    agent_id: str
    trust_score: float
    capability_match: float
    timestamp: float
    assignment_reasoning: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.trust_score <= 1.0:
            raise ValueError(
                f"trust_score must be in [0.0, 1.0], got {self.trust_score}"
            )
        if not 0.0 <= self.capability_match <= 1.0:
            raise ValueError(
                f"capability_match must be in [0.0, 1.0], got {self.capability_match}"
            )


@dataclass
class TrustEntry:
    """Trust ledger entry tracking agent performance."""

    agent_id: str
    task_id: str
    timestamp: float
    success: bool
    quality_score: float
    trust_delta: float
    updated_trust_score: float
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.quality_score <= 1.0:
            raise ValueError(
                f"quality_score must be in [0.0, 1.0], got {self.quality_score}"
            )
        if not -1.0 <= self.trust_delta <= 1.0:
            raise ValueError(
                f"trust_delta must be in [-1.0, 1.0], got {self.trust_delta}"
            )
        if not 0.0 <= self.updated_trust_score <= 1.0:
            raise ValueError(
                f"updated_trust_score must be in [0.0, 1.0], got {self.updated_trust_score}"
            )


@dataclass
class DelegationEvent:
    """Event in a delegation chain."""

    event_id: str
    delegation_id: str
    timestamp: float
    event_type: str
    agent_id: str
    task_id: str
    status: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationResult:
    """Result of subtask verification."""

    subtask_id: str
    timestamp: float
    method: VerificationMethod
    passed: bool
    quality_score: float
    feedback: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.quality_score <= 1.0:
            raise ValueError(
                f"quality_score must be in [0.0, 1.0], got {self.quality_score}"
            )
