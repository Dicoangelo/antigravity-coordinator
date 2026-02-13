"""Tests for optimization modules."""

from __future__ import annotations

import pytest

from coordinator.optimization import (
    Allocation,
    EntropyAllocator,
    PatternDetector,
    PatternResult,
    TaskGraph,
    TaskInfo,
    TopologyResult,
    TopologySelector,
)


class TestEntropyAllocator:
    """Test entropy-based task allocation."""

    def test_low_entropy_allocation(self) -> None:
        """Test allocation for low entropy task."""
        allocator = EntropyAllocator()
        task = TaskInfo(
            id="task1",
            description="Simple task",
            complexity=0.1,
            historical_failure_rate=0.0,
            dq_variance=0.0,
        )

        allocations = allocator.allocate([task], budget=1000.0)

        assert len(allocations) == 1
        assert allocations[0].model == "haiku"
        assert allocations[0].timeout_seconds == 120
        assert allocations[0].agent_count == 1

    def test_medium_entropy_allocation(self) -> None:
        """Test allocation for medium entropy task."""
        allocator = EntropyAllocator()
        task = TaskInfo(
            id="task2",
            description="Medium task",
            complexity=0.5,
            historical_failure_rate=0.3,
            dq_variance=0.4,
        )

        allocations = allocator.allocate([task], budget=1000.0)

        assert len(allocations) == 1
        assert allocations[0].model == "sonnet"
        assert allocations[0].timeout_seconds == 300
        assert allocations[0].agent_count == 1

    def test_high_entropy_allocation(self) -> None:
        """Test allocation for high entropy task."""
        allocator = EntropyAllocator()
        task = TaskInfo(
            id="task3",
            description="Complex task",
            complexity=0.9,
            historical_failure_rate=0.8,
            dq_variance=0.7,
        )

        allocations = allocator.allocate([task], budget=2000.0)

        assert len(allocations) == 1
        assert allocations[0].model == "opus"
        assert allocations[0].timeout_seconds == 600
        assert allocations[0].agent_count == 2

    def test_budget_constraint(self) -> None:
        """Test that allocations respect budget constraint."""
        allocator = EntropyAllocator()
        tasks = [
            TaskInfo(
                id=f"task{i}",
                description=f"Task {i}",
                complexity=0.9,
                historical_failure_rate=0.8,
                dq_variance=0.7,
            )
            for i in range(5)
        ]

        # Budget only allows 2 opus tasks
        allocations = allocator.allocate(tasks, budget=2500.0)

        # Budget constrains total cost; downgrades may yield more allocations
        assert len(allocations) >= 1
        total_cost = sum(
            allocator.MODEL_COSTS[a.model] * a.timeout_seconds for a in allocations
        )
        assert total_cost <= 2500.0

    def test_downgrade_on_budget_limit(self) -> None:
        """Test that tasks are downgraded when budget is tight."""
        allocator = EntropyAllocator()
        task = TaskInfo(
            id="task1",
            description="High entropy task",
            complexity=0.9,
            historical_failure_rate=0.8,
            dq_variance=0.7,
        )

        # Budget too small for opus but enough for sonnet
        allocations = allocator.allocate([task], budget=200.0)

        assert len(allocations) == 1
        assert allocations[0].model == "sonnet"

    def test_entropy_calculation(self) -> None:
        """Test entropy calculation formula."""
        allocator = EntropyAllocator()
        task = TaskInfo(
            id="task1",
            description="Test task",
            complexity=0.5,
            historical_failure_rate=0.3,
            dq_variance=0.2,
        )

        entropy = allocator._calculate_entropy(task)

        # 0.4 * 0.5 + 0.3 * 0.3 + 0.3 * 0.2 = 0.35
        assert abs(entropy - 0.35) < 0.01


class TestTopologySelector:
    """Test topology selection."""

    def test_parallel_topology(self) -> None:
        """Test parallel topology for independent tasks."""
        selector = TopologySelector()
        graph = TaskGraph(
            nodes=["task1", "task2", "task3"],
            edges=[],
        )

        result = selector.select(graph)

        assert result.topology == "parallel"
        assert len(result.agent_assignments) == 3
        assert len(result.execution_order) == 1
        assert isinstance(result.execution_order[0], list)
        assert len(result.execution_order[0]) == 3

    def test_sequential_topology(self) -> None:
        """Test sequential topology for linear chain."""
        selector = TopologySelector()
        graph = TaskGraph(
            nodes=["task1", "task2", "task3"],
            edges=[("task1", "task2"), ("task2", "task3")],
        )

        result = selector.select(graph)

        assert result.topology == "sequential"
        # All tasks use same agent in sequential mode
        assert len(set(result.agent_assignments.values())) == 1

    def test_hierarchical_topology(self) -> None:
        """Test hierarchical topology for high complexity."""
        selector = TopologySelector()
        graph = TaskGraph(
            nodes=["task1", "task2"],
            edges=[("task1", "task2")],
            complexities={"task1": 0.95, "task2": 0.5},
        )

        result = selector.select(graph)

        assert result.topology == "hierarchical"
        assert "supervisor" in result.agent_assignments

    def test_hybrid_topology(self) -> None:
        """Test hybrid topology for mixed dependencies."""
        selector = TopologySelector()
        graph = TaskGraph(
            nodes=["task1", "task2", "task3", "task4"],
            edges=[("task1", "task3"), ("task2", "task4")],
            complexities={"task1": 0.5, "task2": 0.5, "task3": 0.5, "task4": 0.5},
        )

        result = selector.select(graph)

        assert result.topology == "hybrid"
        assert len(result.agent_assignments) == 4

    def test_topological_sort(self) -> None:
        """Test topological sort with parallel groups."""
        selector = TopologySelector()
        graph = TaskGraph(
            nodes=["task1", "task2", "task3", "task4"],
            edges=[("task1", "task3"), ("task2", "task3"), ("task3", "task4")],
        )

        result = selector.select(graph)

        # First level: task1 and task2 in parallel
        # Second level: task3
        # Third level: task4
        assert len(result.execution_order) == 3


class TestPatternDetector:
    """Test pattern detection."""

    def test_debugging_pattern(self) -> None:
        """Test detection of debugging pattern."""
        detector = PatternDetector()
        result = detector.detect("Fix the bug in the authentication system")

        assert result.pattern == "debugging"
        assert result.suggested_strategy == "review"
        assert result.confidence > 0.0

    def test_research_pattern(self) -> None:
        """Test detection of research pattern."""
        detector = PatternDetector()
        result = detector.detect("Research and explore different caching strategies")

        assert result.pattern == "research"
        assert result.suggested_strategy == "research"
        assert result.confidence > 0.0

    def test_architecture_pattern(self) -> None:
        """Test detection of architecture pattern."""
        detector = PatternDetector()
        result = detector.detect("Design a new microservices architecture")

        assert result.pattern == "architecture"
        assert result.suggested_strategy == "full"
        assert result.confidence > 0.0

    def test_implementation_pattern(self) -> None:
        """Test detection of implementation pattern."""
        detector = PatternDetector()
        result = detector.detect("Implement a new feature for user profiles")

        assert result.pattern == "implementation"
        assert result.suggested_strategy == "implement"
        assert result.confidence > 0.0

    def test_testing_pattern(self) -> None:
        """Test detection of testing pattern."""
        detector = PatternDetector()
        result = detector.detect("Add test coverage for the API endpoints")

        assert result.pattern == "testing"
        assert result.suggested_strategy == "review"
        assert result.confidence > 0.0

    def test_optimization_pattern(self) -> None:
        """Test detection of optimization pattern."""
        detector = PatternDetector()
        result = detector.detect("Optimize the database queries for better performance")

        assert result.pattern == "optimization"
        assert result.suggested_strategy == "full"
        assert result.confidence > 0.0

    def test_unknown_pattern(self) -> None:
        """Test detection when no pattern matches."""
        detector = PatternDetector()
        result = detector.detect("Do something completely unrelated")

        assert result.pattern == "unknown"
        assert result.confidence == 0.0
        assert result.suggested_strategy == "implement"

    def test_confidence_calculation(self) -> None:
        """Test that confidence increases with more keyword matches."""
        detector = PatternDetector()

        # Single keyword match
        result1 = detector.detect("fix something")

        # Multiple keyword matches from same pattern
        result2 = detector.detect("fix the bug and debug the error")

        assert result2.confidence > result1.confidence

    def test_mixed_patterns(self) -> None:
        """Test that dominant pattern wins in mixed descriptions."""
        detector = PatternDetector()
        result = detector.detect(
            "Research the issue, debug the problem, and fix the bug"
        )

        # "debugging" has 3 keywords (debug, issue, fix), should dominate
        assert result.pattern == "debugging"
