"""
Task Decomposer — Contract-First Task Decomposition

Implements the contract-first decomposition strategy from arXiv:2602.11865 Section 4.1.

Key principle: "Task delegation contingent upon outcome having precise verification."
If a subtask has verifiability < 0.3, we recursively decompose until all subtasks
are verifiable.
"""

import uuid
from typing import Any, Callable, Dict, List, Optional

from .models import SubTask, TaskProfile, VerificationMethod

MIN_VERIFIABILITY = 0.3
MAX_DEPTH = 4


def _heuristic_decompose(
    task: str,
    profile: TaskProfile,
    parent_id: Optional[str],
    depth: int,
) -> List[SubTask]:
    """Heuristic-based task decomposition (fallback when LLM unavailable)."""
    task_lower = task.lower()

    if any(kw in task_lower for kw in ["build", "create", "develop", "implement system"]):
        templates = [
            ("Design system architecture", VerificationMethod.HUMAN_REVIEW, 0.4, 0.3, False, []),
            ("Implement core functionality", VerificationMethod.AUTOMATED_TEST, 0.5, 0.6, False, ["subtask-0"]),
            ("Add tests and validation", VerificationMethod.AUTOMATED_TEST, 0.3, 0.3, False, ["subtask-1"]),
            ("Deploy and verify", VerificationMethod.GROUND_TRUTH, 0.4, 0.4, False, ["subtask-2"]),
        ]
    elif any(kw in task_lower for kw in ["research", "investigate", "explore", "analyze"]):
        templates = [
            ("Survey existing solutions", VerificationMethod.HUMAN_REVIEW, 0.3, 0.4, True, []),
            ("Analyze findings", VerificationMethod.SEMANTIC_SIMILARITY, 0.4, 0.5, False, ["subtask-0"]),
            ("Synthesize recommendations", VerificationMethod.HUMAN_REVIEW, 0.5, 0.4, False, ["subtask-1"]),
        ]
    elif any(kw in task_lower for kw in ["implement", "code", "write"]):
        templates = [
            ("Plan implementation approach", VerificationMethod.HUMAN_REVIEW, 0.3, 0.2, False, []),
            ("Write code", VerificationMethod.AUTOMATED_TEST, 0.5, 0.6, False, ["subtask-0"]),
            ("Add tests", VerificationMethod.AUTOMATED_TEST, 0.3, 0.3, False, ["subtask-1"]),
        ]
    else:
        templates = [
            ("Understand requirements", VerificationMethod.HUMAN_REVIEW, 0.2, 0.2, False, []),
            ("Execute main task", VerificationMethod.AUTOMATED_TEST, 0.6, 0.6, False, ["subtask-0"]),
            ("Verify completion", VerificationMethod.GROUND_TRUTH, 0.3, 0.2, False, ["subtask-1"]),
        ]

    subtasks = []
    for idx, (desc, method, cost, duration, parallel, deps) in enumerate(templates):
        st_profile = TaskProfile(
            complexity=max(0.2, profile.complexity * 0.6),
            criticality=profile.criticality,
            uncertainty=max(0.2, profile.uncertainty * 0.7),
            duration=duration,
            cost=cost,
            resource_requirements=profile.resource_requirements * 0.5,
            constraints=profile.constraints * 0.5,
            verifiability=0.7,
            reversibility=max(0.5, profile.reversibility),
            contextuality=profile.contextuality * 0.6,
            subjectivity=profile.subjectivity * 0.5,
        )

        subtasks.append(
            SubTask(
                id=f"subtask-{uuid.uuid4().hex[:8]}",
                description=f"{desc} for: {task[:50]}",
                verification_method=method,
                estimated_cost=cost,
                estimated_duration=duration,
                parallel_safe=parallel,
                parent_task_id=parent_id,
                dependencies=deps,
                profile=st_profile,
                metadata={"depth": depth, "heuristic": True},
            )
        )

    return subtasks


def _recursive_decompose(
    task: str,
    profile: TaskProfile,
    parent_id: Optional[str],
    depth: int,
    llm_decompose_fn: Optional[Callable[..., List[SubTask]]],
) -> List[SubTask]:
    """Recursively decompose until all subtasks meet verifiability threshold."""
    if depth >= MAX_DEPTH:
        forced_profile = TaskProfile(
            complexity=profile.complexity,
            criticality=profile.criticality,
            uncertainty=profile.uncertainty,
            duration=profile.duration,
            cost=profile.cost,
            resource_requirements=profile.resource_requirements,
            constraints=profile.constraints,
            verifiability=MIN_VERIFIABILITY,
            reversibility=profile.reversibility,
            contextuality=profile.contextuality,
            subjectivity=profile.subjectivity,
        )
        return [
            SubTask(
                id=f"subtask-{uuid.uuid4().hex[:8]}",
                description=task,
                verification_method=VerificationMethod.HUMAN_REVIEW,
                estimated_cost=profile.cost,
                estimated_duration=profile.duration,
                parallel_safe=True,
                parent_task_id=parent_id,
                dependencies=[],
                profile=forced_profile,
                metadata={"depth": depth, "forced_verifiable": True},
            )
        ]

    if llm_decompose_fn is not None:
        try:
            subtasks = llm_decompose_fn(task, profile, parent_id, depth)
        except Exception:
            subtasks = _heuristic_decompose(task, profile, parent_id, depth)
    else:
        subtasks = _heuristic_decompose(task, profile, parent_id, depth)

    verified_subtasks: List[SubTask] = []
    for st in subtasks:
        if st.profile and st.profile.verifiability < MIN_VERIFIABILITY:
            nested = _recursive_decompose(
                task=st.description,
                profile=st.profile,
                parent_id=st.id,
                depth=depth + 1,
                llm_decompose_fn=llm_decompose_fn,
            )
            verified_subtasks.extend(nested)
        else:
            verified_subtasks.append(st)

    return verified_subtasks


def _analyze_dependencies(subtasks: List[SubTask]) -> List[SubTask]:
    """Analyze dependencies and update parallel_safe flags."""
    id_to_task = {st.id: st for st in subtasks}

    changed = True
    while changed:
        changed = False
        for st in subtasks:
            if st.parallel_safe and st.dependencies:
                deps_parallel = all(
                    id_to_task.get(dep_id, SubTask(
                        id="", description="",
                        verification_method=VerificationMethod.HUMAN_REVIEW,
                        estimated_cost=0.0, estimated_duration=0.0,
                        parallel_safe=False,
                    )).parallel_safe
                    for dep_id in st.dependencies
                )
                if not deps_parallel:
                    st.parallel_safe = False
                    changed = True

    return subtasks


def decompose_task(
    task: str,
    profile: TaskProfile,
    max_depth: int = MAX_DEPTH,
    llm_decompose_fn: Optional[Callable[..., List[SubTask]]] = None,
) -> List[SubTask]:
    """
    Decompose a task into verifiable subtasks following the contract-first principle.

    Args:
        task: Task description to decompose
        profile: TaskProfile for the task
        max_depth: Maximum decomposition depth (default: 4)
        llm_decompose_fn: Optional callable for LLM-based decomposition

    Returns:
        List of SubTask objects, all with verifiability >= 0.3
    """
    subtasks = _recursive_decompose(
        task=task,
        profile=profile,
        parent_id=None,
        depth=0,
        llm_decompose_fn=llm_decompose_fn,
    )
    return _analyze_dependencies(subtasks)
