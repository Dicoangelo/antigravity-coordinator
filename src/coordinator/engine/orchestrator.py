"""Multi-Agent Orchestrator - Main coordinator for parallel Claude agents."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from coordinator.engine.conflict import ConflictManager, detect_potential_conflicts
from coordinator.engine.distribution import TaskAssignment, WorkDistributor, decompose_task
from coordinator.engine.executor import AgentConfig, AgentExecutor, AgentResult
from coordinator.engine.registry import AgentRegistry, AgentState
from coordinator.storage.database import Database


@dataclass
class CoordinationResult:
    """Result of a multi-agent coordination."""

    task_id: str
    task: str
    strategy: str
    status: str  # success, partial, failed
    duration_seconds: float
    agent_results: dict[str, dict[str, Any]]
    synthesis: dict[str, Any]
    total_cost: float


class MultiAgentOrchestrator:
    """
    Main orchestrator for multi-agent coordination.

    Workflow:
    1. Decompose task into subtasks
    2. Detect dependencies (parallel vs sequential)
    3. Check file conflicts
    4. Select strategy (research/implement/review/full)
    5. Execute with appropriate strategy
    6. Synthesize results
    """

    # Cost confirmation threshold
    COST_CONFIRM_THRESHOLD = 1.0  # USD

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or Path.home() / ".coordinator"
        self.db = Database(self.data_dir)
        self.db.ensure_tables()
        self.registry = AgentRegistry(self.data_dir)
        self.conflict_mgr = ConflictManager(self.data_dir)
        self.distributor = WorkDistributor(self.data_dir)
        self.executor = AgentExecutor(self.registry, self.conflict_mgr, self.data_dir)

    def coordinate(
        self,
        task: str,
        strategy: str = "auto",
        confirm_cost: bool = True,
        council_name: str | None = None,
    ) -> CoordinationResult:
        """
        Main coordination entry point.

        Args:
            task: High-level task description
            strategy: "auto", "research", "implement", "review-build", "full", "team", "council"
            confirm_cost: Require confirmation for high-cost operations
            council_name: Specific council for council strategy (auto-detected if None)

        Returns:
            CoordinationResult with status and outputs
        """
        # Store council name for strategy execution
        self._council_name = council_name
        task_id = f"coord-{uuid.uuid4().hex[:8]}"
        start_time = time.time()

        # 1. Decompose task
        subtasks = self._decompose_task(task, strategy)

        # 2. Assign models and estimate costs
        assignments = self.distributor.assign(subtasks)

        # 3. Check conflicts and determine parallelization
        conflict_analysis = detect_potential_conflicts(
            [{"files": a.files, "lock_type": a.lock_type} for a in assignments]
        )

        # 4. Estimate total cost
        cost_estimate = self.distributor.estimate_total_cost(assignments)

        if confirm_cost and cost_estimate["total"] > self.COST_CONFIRM_THRESHOLD:
            print(f"\nEstimated cost: ${cost_estimate['total']:.4f}")
            print(f"Agents: {cost_estimate['agent_count']}")
            print(f"  Haiku: ${cost_estimate['by_model'].get('haiku', 0):.4f}")
            print(f"  Sonnet: ${cost_estimate['by_model'].get('sonnet', 0):.4f}")
            print(f"  Opus: ${cost_estimate['by_model'].get('opus', 0):.4f}")
            response = input("\nProceed? [y/N]: ")
            if response.lower() != "y":
                return CoordinationResult(
                    task_id=task_id,
                    task=task,
                    strategy=strategy,
                    status="cancelled",
                    duration_seconds=0,
                    agent_results={},
                    synthesis={"status": "cancelled", "reason": "User declined"},
                    total_cost=0,
                )

        # 5. Select and execute strategy
        if strategy == "auto":
            strategy = self._detect_strategy(task, assignments, conflict_analysis)

        print(f"\nExecuting strategy: {strategy}")
        print(f"Subtasks: {len(assignments)}")
        print(f"Can parallelize: {conflict_analysis['can_parallelize']}")

        # Execute strategy
        agent_results = self._execute_strategy(
            strategy, task_id, task, assignments, conflict_analysis
        )

        # 6. Synthesize results
        synthesis = self._synthesize_results(agent_results, assignments, strategy)

        duration = time.time() - start_time

        # Calculate actual cost (would need token tracking)
        total_cost = sum(a.cost_estimate for a in assignments)

        result = CoordinationResult(
            task_id=task_id,
            task=task,
            strategy=strategy,
            status=synthesis["status"],
            duration_seconds=round(duration, 2),
            agent_results={k: asdict(v) for k, v in agent_results.items()},
            synthesis=synthesis,
            total_cost=total_cost,
        )

        # Log result
        self._log_coordination(result)

        return result

    def _decompose_task(self, task: str, strategy: str) -> list[dict[str, Any]]:
        """Decompose task based on strategy."""
        if strategy == "council":
            # Council doesn't decompose — all agents get the same task
            return [
                {
                    "subtask": task,
                    "agent_type": "general-purpose",
                    "lock_type": "read",
                    "priority": 0,
                }
            ]
        elif strategy == "research":
            # Multiple explore angles
            return [
                {
                    "subtask": f"Explore architecture for: {task}",
                    "agent_type": "Explore",
                    "lock_type": "read",
                    "priority": 0,
                },
                {
                    "subtask": f"Find similar patterns for: {task}",
                    "agent_type": "Explore",
                    "lock_type": "read",
                    "priority": 0,
                },
                {
                    "subtask": f"Analyze dependencies for: {task}",
                    "agent_type": "Explore",
                    "lock_type": "read",
                    "priority": 0,
                },
            ]
        elif strategy == "implement":
            return [
                {
                    "subtask": f"Implement: {task}",
                    "agent_type": "general-purpose",
                    "lock_type": "write",
                    "priority": 0,
                },
            ]
        elif strategy == "review-build":
            return [
                {
                    "subtask": f"Build: {task}",
                    "agent_type": "general-purpose",
                    "lock_type": "write",
                    "priority": 0,
                },
                {
                    "subtask": f"Review implementation for: {task}",
                    "agent_type": "Explore",
                    "lock_type": "read",
                    "priority": 0,
                },
            ]
        else:
            # Auto decomposition
            return decompose_task(task)

    def _detect_strategy(
        self,
        task: str,
        assignments: Sequence[TaskAssignment],
        conflicts: Mapping[str, Any],
    ) -> str:
        """Auto-detect best strategy for task."""
        task_lower = task.lower()

        # Council indicators — perspective/opinion/evaluation tasks
        council_keywords = [
            "should we",
            "should i",
            "perspectives",
            "opinions",
            "council",
            "review from",
            "what do you think",
            "pros and cons",
            "trade-offs",
            "tradeoffs",
            "advise",
            "recommend",
            "evaluate this",
            "is this the right",
            "compare approaches",
        ]
        if any(kw in task_lower for kw in council_keywords):
            return "council"

        # Research indicators
        if any(
            kw in task_lower
            for kw in ["understand", "explore", "find", "analyze", "investigate", "how does"]
        ):
            return "research"

        # Team indicators — complex multi-part tasks best for Opus 4.6 teams
        if any(
            kw in task_lower
            for kw in ["team", "parallel", "coordinate", "multi-part", "comprehensive"]
        ):
            return "team"

        # Implementation with review
        if any(kw in task_lower for kw in ["implement", "add", "create", "build"]):
            if len(assignments) > 1 and not conflicts["has_conflicts"]:
                return "full"
            return "review-build"

        # Default to full orchestration
        return "full"

    def _execute_strategy(
        self,
        strategy: str,
        task_id: str,
        task: str,
        assignments: Sequence[TaskAssignment],
        conflicts: Mapping[str, Any],
    ) -> dict[str, AgentResult]:
        """Execute the selected strategy."""
        if strategy == "research":
            # All read-only — safe to parallelize
            return self._execute_parallel(task_id, assignments)

        elif strategy == "implement":
            # Parallel if no conflicts, sequential if conflicts
            if conflicts.get("can_parallelize", False):
                return self._execute_parallel(task_id, assignments)
            return self._execute_sequential(task_id, assignments)

        elif strategy in ("review-build", "review"):
            # Builder + reviewer can run in parallel (reviewer is read-only)
            return self._execute_parallel(task_id, assignments)

        elif strategy == "full":
            # Phased: research → implement → review
            return self._execute_phased(task_id, task, assignments, conflicts)

        elif strategy == "team":
            # All parallel with max workers
            return self._execute_parallel(task_id, assignments, max_workers=len(assignments))

        elif strategy == "council":
            # All read-only council agents — fully parallel
            return self._execute_parallel(task_id, assignments)

        else:
            # Unknown strategy — fallback to sequential
            return self._execute_sequential(task_id, assignments)

    def _assignment_to_config(self, assignment: TaskAssignment) -> AgentConfig:
        """Convert a TaskAssignment to an AgentConfig."""
        return AgentConfig(
            subtask=assignment.subtask,
            prompt=assignment.subtask,
            agent_type=assignment.agent_type,
            model=assignment.model,
            files_to_lock=assignment.files,
            lock_type=assignment.lock_type,
            dq_score=assignment.dq_score,
            cost_estimate=assignment.cost_estimate,
        )

    def _collect_results(self, agent_ids: list[str]) -> dict[str, AgentResult]:
        """Collect results from a list of completed agent IDs."""
        results: dict[str, AgentResult] = {}
        for agent_id in agent_ids:
            agent = self.registry.get(agent_id)
            results[agent_id] = AgentResult(
                agent_id=agent_id,
                success=agent.state == AgentState.COMPLETED.value if agent else False,
                output=agent.result.get("output", "") if agent and agent.result else "",
                error=agent.error if agent else "Agent not found",
            )
        return results

    def _execute_parallel(
        self, task_id: str, assignments: Sequence[TaskAssignment], max_workers: int = 5
    ) -> dict[str, AgentResult]:
        """Execute assignments in parallel using the executor's thread pool."""
        configs = [self._assignment_to_config(a) for a in assignments]
        agent_ids = self.executor.spawn_parallel(configs, task_id, max_workers)
        return self._collect_results(agent_ids)

    def _execute_phased(
        self,
        task_id: str,
        task: str,
        assignments: Sequence[TaskAssignment],
        conflicts: Mapping[str, Any],
    ) -> dict[str, AgentResult]:
        """Execute in phases: research (read) first, then implementation (write)."""
        results: dict[str, AgentResult] = {}

        # Phase 1: Research (read-only assignments)
        research = [a for a in assignments if a.lock_type == "read"]
        if research:
            results.update(self._execute_parallel(task_id, research))

        # Phase 2: Implementation (write assignments)
        writes = [a for a in assignments if a.lock_type == "write"]
        if writes:
            if conflicts.get("can_parallelize", False):
                results.update(self._execute_parallel(task_id, writes))
            else:
                results.update(self._execute_sequential(task_id, writes))

        return results

    def _execute_sequential(
        self, task_id: str, assignments: Sequence[TaskAssignment]
    ) -> dict[str, AgentResult]:
        """Execute assignments sequentially."""
        results: dict[str, AgentResult] = {}
        for assignment in assignments:
            config = self._assignment_to_config(assignment)
            agent_id = self.executor.spawn_cli_agent(config, task_id)
            agent = self.registry.get(agent_id)
            results[agent_id] = AgentResult(
                agent_id=agent_id,
                success=agent.state == AgentState.COMPLETED.value if agent else False,
                output=agent.result.get("output", "") if agent and agent.result else "",
                error=agent.error if agent else "Agent not found",
            )
        return results

    def _synthesize_results(
        self,
        agent_results: Mapping[str, AgentResult],
        assignments: Sequence[TaskAssignment],
        strategy: str,
    ) -> dict[str, Any]:
        """Synthesize results from multiple agents."""
        # Simple synthesis for now
        successful = sum(1 for r in agent_results.values() if r.success)
        total = len(agent_results)

        combined_output = "\n\n".join(
            f"## Agent {r.agent_id}\n{r.output}" for r in agent_results.values() if r.success
        )

        errors = [r.error for r in agent_results.values() if r.error]

        if successful == total:
            status = "success"
        elif successful > 0:
            status = "partial"
        else:
            status = "failed"

        return {
            "status": status,
            "successful": successful,
            "total": total,
            "combined_output": combined_output,
            "errors": errors,
        }

    def _log_coordination(self, result: CoordinationResult) -> None:
        """Log coordination result to the sessions table."""
        metadata = json.dumps(
            {
                "duration_seconds": result.duration_seconds,
                "total_cost": result.total_cost,
                "agent_count": len(result.agent_results),
            }
        )
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id, strategy, task, status, metadata)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    status = excluded.status,
                    metadata = excluded.metadata
                """,
                (
                    result.task_id,
                    result.strategy,
                    result.task[:100],
                    result.status,
                    metadata,
                ),
            )

    def status(self, task_id: str | None = None) -> dict[str, Any]:
        """Get status of coordination tasks."""
        if task_id:
            agents = self.registry.get_task_agents(task_id)
            return {
                "task_id": task_id,
                "agents": [asdict(a) for a in agents],
                "stats": self.registry.get_stats(),
            }
        else:
            return {
                "registry": self.registry.get_stats(),
                "locks": self.conflict_mgr.get_stats(),
            }

    def cancel(self, task_id: str) -> None:
        """Cancel a coordination task."""
        self.executor.cancel_task(task_id)
