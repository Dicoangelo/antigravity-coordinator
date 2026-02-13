"""ACE Consensus Engine for session analysis.

Ported from ~/.claude/scripts/observatory/ace_consensus.py
6 analysis agents + DQ-weighted voting for autonomous session evaluation.

"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AnalysisResult:
    """Result from a single analysis agent."""

    agent_name: str
    summary: str
    dq_score: float  # 0-1
    confidence: float  # 0-1
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsensusResult:
    """Final consensus from all agents."""

    outcome: str  # success, partial, error, research, abandoned
    quality: float  # 1-5
    complexity: float  # 0-1
    model_efficiency: float  # 0-1
    dq_score: float  # 0-1
    confidence: float  # 0-1


# DQ weights (validity 40% + specificity 30% + correctness 30%)
DQ_WEIGHTS = {"validity": 0.4, "specificity": 0.3, "correctness": 0.3}


def detect_outcome(session_data: dict[str, Any]) -> AnalysisResult:
    """Detect session outcome from session data.

    Analyzes session transcript to determine outcome:
    - success: Task completed successfully
    - partial: Some progress but incomplete
    - error: Failed with errors
    - research: Research/exploration only
    - abandoned: Session ended without completion

    Args:
        session_data: Session transcript with messages, tools, errors

    Returns:
        AnalysisResult with outcome classification

    """
    messages = session_data.get("messages", [])
    errors = session_data.get("errors", [])
    tools = session_data.get("tools", [])

    # Heuristic outcome detection
    if len(errors) > 5:
        outcome = "error"
        validity = 0.7
    elif len(messages) < 5:
        outcome = "abandoned"
        validity = 0.5
    elif any(t.get("name") == "Read" for t in tools) and not any(
        t.get("name") in ["Write", "Edit"] for t in tools
    ):
        outcome = "research"
        validity = 0.8
    elif any(t.get("name") in ["Write", "Edit"] for t in tools):
        outcome = "success" if len(errors) < 3 else "partial"
        validity = 0.7
    else:
        outcome = "partial"
        validity = 0.5

    dq = DQ_WEIGHTS["validity"] * validity + DQ_WEIGHTS["specificity"] * 0.6

    return AnalysisResult(
        agent_name="outcome_detector",
        summary=f"Outcome: {outcome}",
        dq_score=dq,
        confidence=0.7,
        data={"outcome": outcome},
    )


def score_quality(session_data: dict[str, Any]) -> AnalysisResult:
    """Score session quality (1-5 scale).

    Evaluates:
    - Code quality (clean, documented)
    - Error rate (fewer errors = higher quality)
    - Tool usage patterns (productive vs exploratory)

    Args:
        session_data: Session transcript

    Returns:
        AnalysisResult with quality score

    """
    errors = session_data.get("errors", [])
    messages = session_data.get("messages", [])

    # Simple quality heuristic
    error_rate = len(errors) / max(len(messages), 1)

    if error_rate < 0.1:
        quality = 4.5
        correctness = 0.8
    elif error_rate < 0.2:
        quality = 3.5
        correctness = 0.6
    else:
        quality = 2.5
        correctness = 0.4

    dq = DQ_WEIGHTS["correctness"] * correctness + DQ_WEIGHTS["specificity"] * 0.6

    return AnalysisResult(
        agent_name="quality_scorer",
        summary=f"Quality: {quality}/5",
        dq_score=dq,
        confidence=0.7,
        data={"quality": quality},
    )


def analyze_complexity(session_data: dict[str, Any]) -> AnalysisResult:
    """Analyze task complexity (0-1 scale).

    Complexity indicators:
    - Number of files touched
    - Number of tool calls
    - Message count
    - Error recovery patterns

    Args:
        session_data: Session transcript

    Returns:
        AnalysisResult with complexity score

    """
    messages = session_data.get("messages", [])
    tools = session_data.get("tools", [])

    # Simple complexity heuristic
    msg_count = len(messages)
    tool_count = len(tools)

    if msg_count > 50 or tool_count > 30:
        complexity = 0.8
        specificity = 0.8
    elif msg_count > 20 or tool_count > 15:
        complexity = 0.5
        specificity = 0.6
    else:
        complexity = 0.3
        specificity = 0.5

    dq = DQ_WEIGHTS["specificity"] * specificity + DQ_WEIGHTS["validity"] * 0.6

    return AnalysisResult(
        agent_name="complexity_analyzer",
        summary=f"Complexity: {complexity:.1%}",
        dq_score=dq,
        confidence=0.6,
        data={"complexity": complexity},
    )


def assess_model_efficiency(session_data: dict[str, Any]) -> AnalysisResult:
    """Assess model efficiency for the task.

    Evaluates whether the model used was appropriate:
    - High complexity + Haiku = inefficient
    - Low complexity + Opus = inefficient
    - Matched complexity = efficient

    Args:
        session_data: Session transcript

    Returns:
        AnalysisResult with efficiency score

    """
    metadata = session_data.get("metadata", {})
    model = metadata.get("model", "unknown")

    # Extract complexity from messages/tools
    messages = session_data.get("messages", [])
    complexity = 0.5 if len(messages) < 20 else 0.7

    # Simple efficiency heuristic
    if "opus" in str(model).lower():
        efficiency = 0.9 if complexity > 0.6 else 0.5
        optimal = "opus" if complexity > 0.6 else "sonnet"
    elif "sonnet" in str(model).lower():
        efficiency = 0.8
        optimal = "sonnet"
    elif "haiku" in str(model).lower():
        efficiency = 0.7 if complexity <= 0.5 else 0.4
        optimal = "haiku" if complexity <= 0.5 else "sonnet"
    else:
        efficiency = 0.5
        optimal = "unknown"

    dq = DQ_WEIGHTS["validity"] * 0.6 + DQ_WEIGHTS["correctness"] * efficiency

    return AnalysisResult(
        agent_name="model_efficiency",
        summary=f"Efficiency: {efficiency:.1%}",
        dq_score=dq,
        confidence=0.6,
        data={"efficiency": efficiency, "optimal_model": optimal},
    )


def analyze_productivity(session_data: dict[str, Any]) -> AnalysisResult:
    """Analyze session productivity.

    Metrics:
    - Output/input ratio (code written vs time spent)
    - Tool effectiveness (successful tool calls)
    - Error recovery speed

    Args:
        session_data: Session transcript

    Returns:
        AnalysisResult with productivity score

    """
    tools = session_data.get("tools", [])

    # Count productive tools (Write, Edit) vs exploratory (Read, Grep)
    productive = sum(1 for t in tools if t.get("name") in ["Write", "Edit"])
    exploratory = sum(1 for t in tools if t.get("name") in ["Read", "Grep", "Glob"])

    productivity_score = productive / max(productive + exploratory, 1) if productive > 0 else 0.3

    level = (
        "High" if productivity_score > 0.6 else "Moderate" if productivity_score > 0.3 else "Low"
    )

    dq = DQ_WEIGHTS["specificity"] * productivity_score + DQ_WEIGHTS["validity"] * 0.6

    return AnalysisResult(
        agent_name="productivity_analyzer",
        summary=f"Productivity: {level}",
        dq_score=dq,
        confidence=0.6,
        data={"productivity_score": productivity_score, "level": level},
    )


def assess_routing_quality(session_data: dict[str, Any]) -> AnalysisResult:
    """Assess routing quality (DQ scoring accuracy).

    Evaluates whether the session was routed to the right model based on:
    - Complexity vs model capability
    - Outcome vs expected outcome
    - Cost efficiency

    Args:
        session_data: Session transcript

    Returns:
        AnalysisResult with routing quality assessment

    """
    metadata = session_data.get("metadata", {})
    model = metadata.get("model", "unknown")
    messages = session_data.get("messages", [])

    # Simple routing quality heuristic
    complexity = 0.5 if len(messages) < 20 else 0.7

    if "opus" in str(model).lower() and complexity > 0.6:
        routing_quality = 0.9
    elif "sonnet" in str(model).lower() and 0.3 < complexity < 0.7:
        routing_quality = 0.8
    elif "haiku" in str(model).lower() and complexity < 0.4:
        routing_quality = 0.8
    else:
        routing_quality = 0.5

    dq = DQ_WEIGHTS["validity"] * routing_quality + DQ_WEIGHTS["specificity"] * 0.6

    return AnalysisResult(
        agent_name="routing_quality",
        summary=f"Routing quality: {routing_quality:.1%}",
        dq_score=dq,
        confidence=0.6,
        data={"routing_quality": routing_quality},
    )


def synthesize_consensus(results: list[AnalysisResult]) -> ConsensusResult:
    """Synthesize consensus from agent results using DQ-weighted voting.

    Outcome detector gets 2x weight (primary authority on outcome).
    Other agents contribute based on their DQ scores and confidence.

    Args:
        results: List of AnalysisResult from all agents

    Returns:
        ConsensusResult with final consensus

    """
    if not results:
        return ConsensusResult(
            outcome="unknown",
            quality=3.0,
            complexity=0.5,
            model_efficiency=0.5,
            dq_score=0.5,
            confidence=0.3,
        )

    # Extract values from agents
    outcome = "unknown"
    quality = 3.0
    complexity = 0.5
    model_efficiency = 0.5

    total_dq = 0.0
    total_weight = 0.0

    for result in results:
        weight = result.dq_score * result.confidence

        # Outcome detector has primary authority (2x weight)
        if result.agent_name == "outcome_detector":
            outcome = str(result.data.get("outcome", "unknown"))
            weight *= 2

        # Quality scorer
        if result.agent_name == "quality_scorer":
            quality = float(result.data.get("quality", 3.0))

        # Complexity analyzer
        if result.agent_name == "complexity_analyzer":
            complexity = float(result.data.get("complexity", 0.5))

        # Model efficiency
        if result.agent_name == "model_efficiency":
            model_efficiency = float(result.data.get("efficiency", 0.5))

        total_dq += result.dq_score * weight
        total_weight += weight

    # Calculate overall DQ score
    overall_dq = total_dq / total_weight if total_weight > 0 else 0.5

    # Calculate consensus confidence
    avg_dq = sum(r.dq_score for r in results) / len(results)
    avg_conf = sum(r.confidence for r in results) / len(results)
    confidence = 0.6 * avg_dq + 0.4 * avg_conf

    return ConsensusResult(
        outcome=outcome,
        quality=quality,
        complexity=complexity,
        model_efficiency=model_efficiency,
        dq_score=overall_dq,
        confidence=min(1.0, max(0.0, confidence)),
    )
