"""Tests for the coordination engine."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from coordinator.engine import (
    AgentRegistry,
    AgentState,
    ConflictManager,
    LockType,
    MultiAgentOrchestrator,
    WorkDistributor,
    decompose_task,
    detect_potential_conflicts,
)


@pytest.fixture
def temp_data_dir() -> Path:
    """Create a temporary data directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestRegistry:
    """Tests for AgentRegistry."""

    def test_register_agent(self, temp_data_dir: Path) -> None:
        """Test registering a new agent."""
        registry = AgentRegistry(temp_data_dir)
        agent_id = registry.register(
            task_id="test-task",
            subtask="Test subtask",
            agent_type="general-purpose",
            model="sonnet",
        )

        assert agent_id.startswith("agent-")
        agent = registry.get(agent_id)
        assert agent is not None
        assert agent.task_id == "test-task"
        assert agent.state == AgentState.PENDING.value

    def test_agent_lifecycle(self, temp_data_dir: Path) -> None:
        """Test agent state transitions."""
        registry = AgentRegistry(temp_data_dir)
        agent_id = registry.register(
            task_id="test-task",
            subtask="Test subtask",
            agent_type="general-purpose",
        )

        # Start
        registry.start(agent_id)
        agent = registry.get(agent_id)
        assert agent is not None
        assert agent.state == AgentState.RUNNING.value
        assert agent.started_at is not None

        # Heartbeat
        registry.heartbeat(agent_id, 0.5)
        agent = registry.get(agent_id)
        assert agent is not None
        assert agent.progress == 0.5

        # Complete
        registry.complete(agent_id, {"output": "test output"})
        agent = registry.get(agent_id)
        assert agent is not None
        assert agent.state == AgentState.COMPLETED.value
        assert agent.progress == 1.0

    def test_get_task_agents(self, temp_data_dir: Path) -> None:
        """Test retrieving all agents for a task."""
        registry = AgentRegistry(temp_data_dir)

        task_id = "test-task"
        agent_ids = [
            registry.register(task_id=task_id, subtask=f"Subtask {i}", agent_type="general-purpose")
            for i in range(3)
        ]

        agents = registry.get_task_agents(task_id)
        assert len(agents) == 3
        assert {a.agent_id for a in agents} == set(agent_ids)

    def test_cleanup_completed(self, temp_data_dir: Path) -> None:
        """Test cleanup of old completed agents."""
        registry = AgentRegistry(temp_data_dir)

        agent_id = registry.register(
            task_id="test-task",
            subtask="Test subtask",
            agent_type="general-purpose",
        )

        registry.start(agent_id)
        registry.complete(agent_id)

        # Cleanup should not remove recent completions
        removed = registry.cleanup_completed(older_than_seconds=3600)
        assert removed == 0

        # But should remove old ones
        removed = registry.cleanup_completed(older_than_seconds=0)
        assert removed == 1

    def test_get_stats(self, temp_data_dir: Path) -> None:
        """Test registry statistics."""
        registry = AgentRegistry(temp_data_dir)

        registry.register(task_id="task-1", subtask="Sub 1", agent_type="general-purpose", model="haiku")
        registry.register(task_id="task-1", subtask="Sub 2", agent_type="general-purpose", model="sonnet")

        stats = registry.get_stats()
        assert stats["total_agents"] == 2
        assert stats["by_model"]["haiku"] == 1
        assert stats["by_model"]["sonnet"] == 1
        assert stats["by_state"][AgentState.PENDING.value] == 2


class TestConflictManager:
    """Tests for ConflictManager."""

    def test_acquire_read_lock(self, temp_data_dir: Path) -> None:
        """Test acquiring a read lock."""
        mgr = ConflictManager(temp_data_dir)

        success = mgr.acquire("/tmp/test.txt", "agent-1", LockType.READ.value)
        assert success

        locks = mgr.get_file_locks("/tmp/test.txt")
        assert len(locks) == 1
        assert locks[0].agent_id == "agent-1"

    def test_multiple_readers(self, temp_data_dir: Path) -> None:
        """Test multiple read locks on same file."""
        mgr = ConflictManager(temp_data_dir)

        assert mgr.acquire("/tmp/test.txt", "agent-1", LockType.READ.value)
        assert mgr.acquire("/tmp/test.txt", "agent-2", LockType.READ.value)

        locks = mgr.get_file_locks("/tmp/test.txt")
        assert len(locks) == 2

    def test_write_lock_blocks_readers(self, temp_data_dir: Path) -> None:
        """Test that write lock prevents new readers."""
        mgr = ConflictManager(temp_data_dir)

        assert mgr.acquire("/tmp/test.txt", "agent-1", LockType.WRITE.value)
        assert not mgr.acquire("/tmp/test.txt", "agent-2", LockType.READ.value)

    def test_reader_blocks_writer(self, temp_data_dir: Path) -> None:
        """Test that read lock prevents writers."""
        mgr = ConflictManager(temp_data_dir)

        assert mgr.acquire("/tmp/test.txt", "agent-1", LockType.READ.value)
        assert not mgr.acquire("/tmp/test.txt", "agent-2", LockType.WRITE.value)

    def test_release_lock(self, temp_data_dir: Path) -> None:
        """Test releasing a lock."""
        mgr = ConflictManager(temp_data_dir)

        mgr.acquire("/tmp/test.txt", "agent-1", LockType.WRITE.value)
        mgr.release("/tmp/test.txt", "agent-1")

        locks = mgr.get_file_locks("/tmp/test.txt")
        assert len(locks) == 0

        # Now another agent can acquire
        assert mgr.acquire("/tmp/test.txt", "agent-2", LockType.WRITE.value)

    def test_release_agent_locks(self, temp_data_dir: Path) -> None:
        """Test releasing all locks for an agent."""
        mgr = ConflictManager(temp_data_dir)

        mgr.acquire("/tmp/test1.txt", "agent-1", LockType.READ.value)
        mgr.acquire("/tmp/test2.txt", "agent-1", LockType.READ.value)

        locks = mgr.get_agent_locks("agent-1")
        assert len(locks) == 2

        mgr.release_agent("agent-1")

        locks = mgr.get_agent_locks("agent-1")
        assert len(locks) == 0

    def test_detect_potential_conflicts(self) -> None:
        """Test pre-flight conflict detection."""
        subtasks = [
            {"files": ["file1.txt"], "lock_type": LockType.READ.value},
            {"files": ["file1.txt"], "lock_type": LockType.READ.value},
            {"files": ["file1.txt"], "lock_type": LockType.WRITE.value},
        ]

        result = detect_potential_conflicts(subtasks)

        assert result["has_conflicts"] is True
        assert len(result["conflicts"]) > 0

    def test_no_conflicts_all_readers(self) -> None:
        """Test that all readers have no conflicts."""
        subtasks = [
            {"files": ["file1.txt"], "lock_type": LockType.READ.value},
            {"files": ["file1.txt"], "lock_type": LockType.READ.value},
        ]

        result = detect_potential_conflicts(subtasks)

        assert result["has_conflicts"] is False
        assert result["can_parallelize"] is True

    def test_parallel_groups(self) -> None:
        """Test parallel group detection."""
        subtasks = [
            {"files": ["file1.txt"], "lock_type": LockType.WRITE.value},
            {"files": ["file2.txt"], "lock_type": LockType.WRITE.value},
            {"files": ["file1.txt"], "lock_type": LockType.READ.value},
        ]

        result = detect_potential_conflicts(subtasks)

        # Should have 2 groups: [0, 1] and [2] (since 0 and 2 conflict on file1)
        assert len(result["parallel_groups"]) == 2
        assert result["can_parallelize"] is True


class TestWorkDistributor:
    """Tests for WorkDistributor."""

    def test_estimate_complexity(self, temp_data_dir: Path) -> None:
        """Test complexity estimation."""
        dist = WorkDistributor(temp_data_dir)

        # Simple task
        complexity = dist.estimate_complexity("Read file contents")
        assert complexity < 0.5

        # Complex task
        complexity = dist.estimate_complexity("Refactor entire architecture for scalability")
        assert complexity >= 0.5

    def test_select_model(self, temp_data_dir: Path) -> None:
        """Test model selection based on complexity."""
        dist = WorkDistributor(temp_data_dir)

        # Low complexity -> haiku
        model = dist.select_model(0.2)
        assert model == "haiku"

        # Medium complexity -> sonnet
        model = dist.select_model(0.5)
        assert model == "sonnet"

        # High complexity -> opus
        model = dist.select_model(0.8)
        assert model == "opus"

    def test_assign_subtasks(self, temp_data_dir: Path) -> None:
        """Test assigning models to subtasks."""
        dist = WorkDistributor(temp_data_dir)

        subtasks = [
            {"subtask": "Read configuration file", "lock_type": "read"},
            {"subtask": "Implement complex distributed system", "lock_type": "write"},
        ]

        assignments = dist.assign(subtasks)

        assert len(assignments) == 2
        assert all(a.model in ["haiku", "sonnet", "opus"] for a in assignments)
        assert all(a.dq_score > 0 for a in assignments)

    def test_estimate_total_cost(self, temp_data_dir: Path) -> None:
        """Test total cost estimation."""
        dist = WorkDistributor(temp_data_dir)

        subtasks = [
            {"subtask": "Task 1", "lock_type": "read"},
            {"subtask": "Task 2", "lock_type": "write"},
        ]

        assignments = dist.assign(subtasks)
        cost = dist.estimate_total_cost(assignments)

        assert cost["total"] > 0
        assert cost["agent_count"] == 2
        assert "by_model" in cost

    def test_decompose_task(self) -> None:
        """Test task decomposition."""
        # Implementation task
        subtasks = decompose_task("Implement user authentication system")
        assert len(subtasks) > 1
        assert any("implement" in s["subtask"].lower() for s in subtasks)

        # Research task
        subtasks = decompose_task("Analyze performance bottlenecks")
        assert any("research" in s["subtask"].lower() or "explore" in s["subtask"].lower() for s in subtasks)


class TestOrchestrator:
    """Tests for MultiAgentOrchestrator."""

    def test_orchestrator_initialization(self, temp_data_dir: Path) -> None:
        """Test orchestrator initialization."""
        orch = MultiAgentOrchestrator(temp_data_dir)

        assert orch.registry is not None
        assert orch.conflict_mgr is not None
        assert orch.distributor is not None
        assert orch.executor is not None

    def test_detect_strategy(self, temp_data_dir: Path) -> None:
        """Test strategy auto-detection."""
        orch = MultiAgentOrchestrator(temp_data_dir)

        # Research task
        strategy = orch._detect_strategy("Explore how the database works", [], {})
        assert strategy == "research"

        # Implementation task
        strategy = orch._detect_strategy("Implement user profile feature", [], {"has_conflicts": False})
        assert strategy in ["review-build", "full"]

    def test_status(self, temp_data_dir: Path) -> None:
        """Test getting orchestrator status."""
        orch = MultiAgentOrchestrator(temp_data_dir)

        status = orch.status()
        assert "registry" in status
        assert "locks" in status
