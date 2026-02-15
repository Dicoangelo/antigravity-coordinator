"""
Agent Router — Capability Matching with Trust-Weighted Scoring

Implements the routing strategy from arXiv:2602.11865 Section 4.2.

Scoring formula:
    final_score = capability_match * 0.6 + trust_score * 0.3 + cost_efficiency * 0.1
"""

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .models import Assignment, SubTask

# Complexity floor for direct execution (no delegation)
MIN_COMPLEXITY_FOR_DELEGATION = 0.2

# Agent scoring weights (must sum to 1.0)
CAPABILITY_WEIGHT = 0.6
TRUST_WEIGHT = 0.3
COST_WEIGHT = 0.1


@dataclass
class AgentCapability:
    """Agent capability profile."""

    agent_id: str
    name: str
    description: str
    keywords: List[str] = field(default_factory=list)
    estimated_cost: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)


def _extract_keywords(text: str) -> List[str]:
    """Extract keywords from text for capability matching."""
    stopwords = {
        "the", "and", "for", "from", "with", "this", "that",
        "are", "was", "will", "can", "has", "have", "been",
        "get", "set", "list", "find", "search", "load", "create",
    }
    words = re.findall(r"\w+", text.lower())
    keywords = [w for w in words if len(w) >= 4 and w not in stopwords]
    return list(set(keywords))


def _calculate_capability_match(subtask: SubTask, agent: AgentCapability) -> float:
    """Calculate how well agent capabilities match subtask requirements."""
    subtask_keywords = _extract_keywords(subtask.description)

    if not subtask_keywords or not agent.keywords:
        return 0.0

    overlap = set(subtask_keywords) & set(agent.keywords)
    return len(overlap) / max(len(subtask_keywords), len(agent.keywords))


def route_subtask(
    subtask: SubTask,
    available_agents: List[AgentCapability],
    trust_scores: Optional[Dict[str, float]] = None,
) -> Assignment:
    """
    Route a subtask to the optimal agent.

    Args:
        subtask: SubTask to route
        available_agents: List of AgentCapability profiles
        trust_scores: Optional dict mapping agent_id -> trust score [0.0, 1.0]

    Returns:
        Assignment with selected agent and scoring breakdown
    """
    if trust_scores is None:
        trust_scores = {}

    # Complexity floor: tasks below threshold execute directly
    if subtask.profile and subtask.profile.complexity < MIN_COMPLEXITY_FOR_DELEGATION:
        return Assignment(
            subtask_id=subtask.id,
            agent_id="DIRECT_EXECUTION",
            trust_score=1.0,
            capability_match=1.0,
            timestamp=time.time(),
            assignment_reasoning=(
                f"Complexity {subtask.profile.complexity:.2f} below delegation "
                f"threshold {MIN_COMPLEXITY_FOR_DELEGATION} -> direct execution"
            ),
            metadata={"delegation_bypassed": True},
        )

    scored_agents = []
    for agent in available_agents:
        capability_match = _calculate_capability_match(subtask, agent)
        trust_score = trust_scores.get(agent.agent_id, 0.5)

        if subtask.profile:
            cost_diff = abs(subtask.estimated_cost - agent.estimated_cost)
            cost_efficiency = 1.0 - cost_diff
        else:
            cost_efficiency = 0.5

        final_score = (
            capability_match * CAPABILITY_WEIGHT
            + trust_score * TRUST_WEIGHT
            + cost_efficiency * COST_WEIGHT
        )

        scored_agents.append(
            {
                "agent": agent,
                "capability_match": capability_match,
                "trust_score": trust_score,
                "cost_efficiency": cost_efficiency,
                "final_score": final_score,
            }
        )

    scored_agents.sort(key=lambda x: x["final_score"], reverse=True)

    if not scored_agents:
        return Assignment(
            subtask_id=subtask.id,
            agent_id="DIRECT_EXECUTION",
            trust_score=0.5,
            capability_match=0.0,
            timestamp=time.time(),
            assignment_reasoning="No agents available -> fallback to direct execution",
            metadata={"no_agents_available": True},
        )

    best = scored_agents[0]
    agent = best["agent"]

    reasoning = (
        f"Selected {agent.name} (score: {best['final_score']:.3f}) | "
        f"Capability: {best['capability_match']:.3f}, "
        f"Trust: {best['trust_score']:.3f}, "
        f"Cost: {best['cost_efficiency']:.3f}"
    )

    return Assignment(
        subtask_id=subtask.id,
        agent_id=agent.agent_id,
        trust_score=best["trust_score"],
        capability_match=best["capability_match"],
        timestamp=time.time(),
        assignment_reasoning=reasoning,
        metadata={
            "final_score": best["final_score"],
            "cost_efficiency": best["cost_efficiency"],
            "agent_name": agent.name,
            "agent_description": agent.description,
            "fallback_chain": [s["agent"].agent_id for s in scored_agents[1:4]],
        },
    )


def route_batch(
    subtasks: List[SubTask],
    available_agents: List[AgentCapability],
    trust_scores: Optional[Dict[str, float]] = None,
) -> List[Assignment]:
    """Route multiple subtasks in batch."""
    return [
        route_subtask(subtask, available_agents, trust_scores)
        for subtask in subtasks
    ]
