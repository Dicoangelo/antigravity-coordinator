"""Topology selection for task execution inspired by Agyn."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TaskGraph:
    """Task dependency graph."""

    nodes: list[str]  # List of task IDs
    edges: list[tuple[str, str]]  # List of (from, to) dependency pairs
    complexities: dict[str, float] | None = None  # Optional complexity per task (0-1)


@dataclass
class TopologyResult:
    """Result of topology selection."""

    topology: str  # parallel/sequential/hybrid/hierarchical
    agent_assignments: dict[str, str]  # task_id -> agent_id
    execution_order: list[str | list[str]]  # Execution order (nested lists = parallel)


class TopologySelector:
    """Selects execution topology based on task graph structure."""

    def __init__(self) -> None:
        """Initialize the topology selector."""
        pass

    def _is_linear_chain(self, graph: TaskGraph) -> bool:
        """Check if graph is a single linear chain (sequential).

        Args:
            graph: Task dependency graph

        Returns:
            True if graph is a single connected linear chain
        """
        if not graph.edges:
            return False

        # A single linear chain of N nodes has exactly N-1 edges
        if len(graph.edges) != len(graph.nodes) - 1:
            return False

        # Count in-edges and out-edges for each node
        in_degree: dict[str, int] = {node: 0 for node in graph.nodes}
        out_degree: dict[str, int] = {node: 0 for node in graph.nodes}

        for from_node, to_node in graph.edges:
            out_degree[from_node] += 1
            in_degree[to_node] += 1

        # Linear chain: each node has at most 1 in-edge and 1 out-edge
        for node in graph.nodes:
            if in_degree[node] > 1 or out_degree[node] > 1:
                return False

        return True

    def _has_high_complexity_node(self, graph: TaskGraph) -> bool:
        """Check if any node has complexity > 0.9.

        Args:
            graph: Task dependency graph

        Returns:
            True if any node has complexity > 0.9
        """
        if not graph.complexities:
            return False

        return any(c > 0.9 for c in graph.complexities.values())

    def _topological_sort(self, graph: TaskGraph) -> list[str | list[str]]:
        """Perform topological sort, grouping independent tasks.

        Args:
            graph: Task dependency graph

        Returns:
            Execution order with parallel groups
        """
        # Build adjacency lists
        in_degree: dict[str, int] = {node: 0 for node in graph.nodes}
        children: dict[str, list[str]] = {node: [] for node in graph.nodes}

        for from_node, to_node in graph.edges:
            children[from_node].append(to_node)
            in_degree[to_node] += 1

        # Find all nodes with no dependencies
        queue = [node for node in graph.nodes if in_degree[node] == 0]
        result: list[str | list[str]] = []

        while queue:
            # Process all independent nodes in parallel
            if len(queue) == 1:
                result.append(queue[0])
            else:
                result.append(queue[:])

            # Update dependencies
            next_queue: list[str] = []
            for node in queue:
                for child in children[node]:
                    in_degree[child] -= 1
                    if in_degree[child] == 0:
                        next_queue.append(child)

            queue = next_queue

        return result

    def select(self, graph: TaskGraph) -> TopologyResult:
        """Select optimal topology for task execution.

        Args:
            graph: Task dependency graph

        Returns:
            Topology selection result
        """
        # No edges → parallel
        if not graph.edges:
            topology = "parallel"
            agent_assignments = {node: f"agent_{i}" for i, node in enumerate(graph.nodes)}
            execution_order: list[str | list[str]] = [graph.nodes[:]]

        # High complexity → hierarchical (opus supervisor) — check BEFORE linear chain
        elif self._has_high_complexity_node(graph):
            topology = "hierarchical"
            execution_order = self._topological_sort(graph)
            # Supervisor + workers
            agent_assignments = {"supervisor": "agent_supervisor"}
            agent_assignments.update({node: f"agent_{i}" for i, node in enumerate(graph.nodes)})

        # Linear chain → sequential
        elif self._is_linear_chain(graph):
            topology = "sequential"
            execution_order = self._topological_sort(graph)
            agent_assignments = {node: "agent_0" for node in graph.nodes}

        # Otherwise → hybrid
        else:
            topology = "hybrid"
            execution_order = self._topological_sort(graph)
            # Assign agents to independent groups
            agent_count = 0
            agent_assignments = {}
            for item in execution_order:
                if isinstance(item, list):
                    # Parallel group - different agents
                    for node in item:
                        agent_assignments[node] = f"agent_{agent_count}"
                        agent_count += 1
                else:
                    # Sequential node - reuse agent
                    agent_assignments[item] = f"agent_{agent_count % max(1, agent_count)}"

        return TopologyResult(
            topology=topology,
            agent_assignments=agent_assignments,
            execution_order=execution_order,
        )
