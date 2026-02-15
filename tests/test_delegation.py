"""
Tests for the delegation module.

Covers: models, taxonomy, decomposer, router, four_ds, trust_ledger, evolution, executor.
"""

import asyncio
import json
import sqlite3
import tempfile
import time
from pathlib import Path

import pytest

from coordinator.delegation.models import (
    Assignment,
    DelegationEvent,
    SubTask,
    TaskProfile,
    TrustEntry,
    VerificationMethod,
    VerificationResult,
)
from coordinator.delegation.taxonomy import (
    classify_task,
    compute_delegation_overhead,
    compute_risk_score,
)
from coordinator.delegation.decomposer import decompose_task
from coordinator.delegation.router import (
    AgentCapability,
    route_batch,
    route_subtask,
)
from coordinator.delegation.four_ds import (
    FourDsGate,
    delegation_gate,
    description_gate,
    discernment_gate,
    diligence_gate,
)
from coordinator.delegation.trust_ledger import AgentTrustScore, TrustLedger
from coordinator.delegation.evolution import EvolutionEngine
from coordinator.delegation.executor import ExecutionResult, SubtaskExecutor

pytestmark = pytest.mark.anyio


# ═══════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════


class TestTaskProfile:
    def test_default_values(self):
        p = TaskProfile()
        assert p.complexity == 0.5
        assert p.criticality == 0.5

    def test_custom_values(self):
        p = TaskProfile(complexity=0.8, criticality=0.2)
        assert p.complexity == 0.8
        assert p.criticality == 0.2

    def test_validation_raises(self):
        with pytest.raises(ValueError, match="complexity"):
            TaskProfile(complexity=1.5)
        with pytest.raises(ValueError, match="criticality"):
            TaskProfile(criticality=-0.1)

    def test_all_dimensions(self):
        p = TaskProfile(
            complexity=0.1, criticality=0.2, uncertainty=0.3,
            duration=0.4, cost=0.5, resource_requirements=0.6,
            constraints=0.7, verifiability=0.8, reversibility=0.9,
            contextuality=0.1, subjectivity=0.2,
        )
        assert p.constraints == 0.7
        assert p.verifiability == 0.8


class TestSubTask:
    def test_creation(self):
        st = SubTask(
            id="st-1", description="Test task",
            verification_method=VerificationMethod.AUTOMATED_TEST,
            estimated_cost=0.3, estimated_duration=0.5, parallel_safe=True,
        )
        assert st.id == "st-1"
        assert st.parallel_safe is True

    def test_cost_validation(self):
        with pytest.raises(ValueError, match="estimated_cost"):
            SubTask(
                id="st-1", description="x",
                verification_method=VerificationMethod.HUMAN_REVIEW,
                estimated_cost=2.0, estimated_duration=0.5, parallel_safe=False,
            )


class TestAssignment:
    def test_creation(self):
        a = Assignment(
            subtask_id="st-1", agent_id="agent-1",
            trust_score=0.8, capability_match=0.7, timestamp=time.time(),
        )
        assert a.trust_score == 0.8

    def test_validation(self):
        with pytest.raises(ValueError, match="trust_score"):
            Assignment(
                subtask_id="st-1", agent_id="agent-1",
                trust_score=1.5, capability_match=0.7, timestamp=time.time(),
            )


class TestVerificationResult:
    def test_creation(self):
        vr = VerificationResult(
            subtask_id="st-1", timestamp=time.time(),
            method=VerificationMethod.GROUND_TRUTH,
            passed=True, quality_score=0.95,
        )
        assert vr.passed is True

    def test_quality_validation(self):
        with pytest.raises(ValueError, match="quality_score"):
            VerificationResult(
                subtask_id="st-1", timestamp=time.time(),
                method=VerificationMethod.HUMAN_REVIEW,
                passed=True, quality_score=1.5,
            )


class TestDelegationEvent:
    def test_creation(self):
        de = DelegationEvent(
            event_id="ev-1", delegation_id="del-1", timestamp=time.time(),
            event_type="created", agent_id="agent-1",
            task_id="task-1", status="pending",
        )
        assert de.event_type == "created"


# ═══════════════════════════════════════════════════════════════════════════
# TAXONOMY
# ═══════════════════════════════════════════════════════════════════════════


class TestTaxonomy:
    def test_classify_simple_task(self):
        profile = classify_task("Read the configuration file")
        assert 0.0 <= profile.complexity <= 1.0
        assert profile.complexity < 0.5  # "read" is low complexity

    def test_classify_complex_task(self):
        profile = classify_task("Implement a distributed authentication system")
        assert profile.complexity >= 0.5

    def test_classify_research_task(self):
        profile = classify_task("Research multi-agent trust calibration approaches")
        assert profile.uncertainty >= 0.5

    def test_classify_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            classify_task("")

    def test_classify_with_context(self):
        profile = classify_task(
            "Add API endpoint",
            context={"is_critical": True},
        )
        assert profile.criticality >= 0.7

    def test_delegation_overhead_simple(self):
        p = TaskProfile(complexity=0.1)
        assert compute_delegation_overhead(p) == 0.1

    def test_delegation_overhead_complex(self):
        p = TaskProfile(complexity=0.8, duration=0.7, cost=0.6)
        overhead = compute_delegation_overhead(p)
        assert overhead < 0.5

    def test_risk_score(self):
        p = TaskProfile(criticality=0.9, reversibility=0.1, uncertainty=0.8)
        risk = compute_risk_score(p)
        assert risk > 0.6


# ═══════════════════════════════════════════════════════════════════════════
# DECOMPOSER
# ═══════════════════════════════════════════════════════════════════════════


class TestDecomposer:
    def test_decompose_build_task(self):
        profile = TaskProfile(complexity=0.7, verifiability=0.6)
        subtasks = decompose_task("Build API server", profile)
        assert len(subtasks) >= 3
        assert all(
            st.profile is not None and st.profile.verifiability >= 0.3
            for st in subtasks
        )

    def test_decompose_research_task(self):
        profile = TaskProfile(complexity=0.5, uncertainty=0.8)
        subtasks = decompose_task("Research AI delegation", profile)
        assert len(subtasks) >= 2

    def test_decompose_default_pattern(self):
        profile = TaskProfile(complexity=0.5)
        subtasks = decompose_task("Do a thing", profile)
        assert len(subtasks) >= 2

    def test_decompose_preserves_verifiability(self):
        profile = TaskProfile(complexity=0.7, verifiability=0.6)
        subtasks = decompose_task("Implement core module", profile)
        for st in subtasks:
            assert st.profile is not None
            assert st.profile.verifiability >= 0.3

    def test_decompose_with_dependencies(self):
        profile = TaskProfile(complexity=0.7)
        subtasks = decompose_task("Build and deploy app", profile)
        has_deps = any(st.dependencies for st in subtasks)
        assert has_deps


# ═══════════════════════════════════════════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════════════════════════════════════════


class TestRouter:
    def _make_agents(self):
        return [
            AgentCapability(
                agent_id="search::find", name="find",
                description="Search and find research papers on AI topics",
                keywords=["search", "research", "papers", "topics"],
                estimated_cost=0.3,
            ),
            AgentCapability(
                agent_id="code::implement", name="implement",
                description="Implement code solutions and algorithms",
                keywords=["implement", "code", "solutions", "algorithms"],
                estimated_cost=0.5,
            ),
        ]

    def test_route_to_best_agent(self):
        agents = self._make_agents()
        subtask = SubTask(
            id="st-1", description="Search for AI research papers",
            verification_method=VerificationMethod.HUMAN_REVIEW,
            estimated_cost=0.3, estimated_duration=0.3, parallel_safe=True,
            profile=TaskProfile(complexity=0.5),
        )
        assignment = route_subtask(subtask, agents)
        assert assignment.agent_id == "search::find"

    def test_route_complexity_floor(self):
        agents = self._make_agents()
        subtask = SubTask(
            id="st-1", description="Simple lookup",
            verification_method=VerificationMethod.HUMAN_REVIEW,
            estimated_cost=0.1, estimated_duration=0.1, parallel_safe=True,
            profile=TaskProfile(complexity=0.1),
        )
        assignment = route_subtask(subtask, agents)
        assert assignment.agent_id == "DIRECT_EXECUTION"

    def test_route_no_agents(self):
        subtask = SubTask(
            id="st-1", description="Anything",
            verification_method=VerificationMethod.HUMAN_REVIEW,
            estimated_cost=0.3, estimated_duration=0.3, parallel_safe=True,
            profile=TaskProfile(complexity=0.5),
        )
        assignment = route_subtask(subtask, [])
        assert assignment.agent_id == "DIRECT_EXECUTION"

    def test_route_with_trust_scores(self):
        agents = self._make_agents()
        subtask = SubTask(
            id="st-1", description="Implement an algorithm for sorting",
            verification_method=VerificationMethod.AUTOMATED_TEST,
            estimated_cost=0.5, estimated_duration=0.5, parallel_safe=True,
            profile=TaskProfile(complexity=0.6),
        )
        trust = {"code::implement": 0.95, "search::find": 0.3}
        assignment = route_subtask(subtask, agents, trust_scores=trust)
        assert assignment.agent_id == "code::implement"

    def test_route_batch(self):
        agents = self._make_agents()
        subtasks = [
            SubTask(
                id="st-1", description="Search for papers",
                verification_method=VerificationMethod.HUMAN_REVIEW,
                estimated_cost=0.3, estimated_duration=0.3, parallel_safe=True,
                profile=TaskProfile(complexity=0.5),
            ),
            SubTask(
                id="st-2", description="Implement solution",
                verification_method=VerificationMethod.AUTOMATED_TEST,
                estimated_cost=0.5, estimated_duration=0.5, parallel_safe=True,
                profile=TaskProfile(complexity=0.6),
            ),
        ]
        assignments = route_batch(subtasks, agents)
        assert len(assignments) == 2


# ═══════════════════════════════════════════════════════════════════════════
# FOUR DS
# ═══════════════════════════════════════════════════════════════════════════


class TestFourDs:
    def test_delegation_gate_approved(self):
        profile = TaskProfile(subjectivity=0.3, criticality=0.4, reversibility=0.8)
        approved, reason = delegation_gate("Simple code task", profile)
        assert approved is True

    def test_delegation_gate_blocked_high_risk(self):
        profile = TaskProfile(subjectivity=0.9, criticality=0.9, reversibility=0.1)
        approved, reason = delegation_gate("Critical subjective task", profile)
        assert approved is False
        assert "human judgment" in reason

    def test_delegation_gate_blocked_critical_unverifiable(self):
        profile = TaskProfile(criticality=0.9, verifiability=0.2, reversibility=0.5)
        approved, reason = delegation_gate("Critical task", profile)
        assert approved is False

    def test_description_gate_good(self):
        score, suggestions = description_gate(
            "Implement authentication system that must handle at least 1000 concurrent users "
            "and should verify user credentials against the database"
        )
        assert score >= 0.5

    def test_description_gate_poor(self):
        score, suggestions = description_gate("fix stuff")
        assert score < 0.5

    def test_discernment_gate_acceptable(self):
        score, issues = discernment_gate(
            output="The authentication system uses JWT tokens for secure access",
            expected="Authentication system with JWT tokens",
            profile=TaskProfile(),
        )
        assert score > 0.5

    def test_discernment_gate_error_output(self):
        score, issues = discernment_gate(
            output="Error: undefined variable in module",
            expected="Working implementation",
            profile=TaskProfile(),
        )
        assert any("error" in issue.lower() for issue in issues)

    def test_diligence_gate_safe(self):
        profile = TaskProfile(reversibility=0.8)
        safe, warnings = diligence_gate("Implement new feature", profile)
        assert safe is True

    def test_diligence_gate_blocked_destructive(self):
        profile = TaskProfile(reversibility=0.1)
        safe, warnings = diligence_gate(
            "Delete all user credentials from the database", profile
        )
        assert safe is False

    def test_diligence_gate_production_warning(self):
        profile = TaskProfile(verifiability=0.4)
        safe, warnings = diligence_gate("Deploy to production", profile)
        assert safe is True
        assert any("production" in w.lower() for w in warnings)


# ═══════════════════════════════════════════════════════════════════════════
# TRUST LEDGER
# ═══════════════════════════════════════════════════════════════════════════


class TestTrustLedger:
    async def test_record_and_get_trust(self):
        async with TrustLedger(":memory:") as ledger:
            score = await ledger.record_outcome("agent-1", "code", True, 0.9, 5.0)
            assert score > 0.5

    async def test_uninformative_prior(self):
        async with TrustLedger(":memory:") as ledger:
            score = await ledger.get_trust_score("unknown", "code")
            assert score == 0.5

    async def test_bayesian_update(self):
        async with TrustLedger(":memory:") as ledger:
            for _ in range(10):
                await ledger.record_outcome("agent-1", "code", True, 0.9, 1.0)
            score = await ledger.get_trust_score("agent-1", "code")
            assert score > 0.85

    async def test_failed_outcomes_lower_trust(self):
        async with TrustLedger(":memory:") as ledger:
            for _ in range(5):
                await ledger.record_outcome("agent-1", "code", False, 0.2, 1.0)
            score = await ledger.get_trust_score("agent-1", "code")
            assert score < 0.3

    async def test_get_top_agents(self):
        async with TrustLedger(":memory:") as ledger:
            for _ in range(5):
                await ledger.record_outcome("good-agent", "research", True, 0.95, 1.0)
            for _ in range(5):
                await ledger.record_outcome("bad-agent", "research", False, 0.2, 1.0)

            top = await ledger.get_top_agents("research", limit=5)
            assert len(top) == 2
            assert top[0]["agent_id"] == "good-agent"

    async def test_get_agent_stats(self):
        async with TrustLedger(":memory:") as ledger:
            await ledger.record_outcome("agent-1", "code", True, 0.9, 5.0)
            stats = await ledger.get_agent_stats("agent-1", "code")
            assert stats is not None
            assert stats.success_count == 1
            assert stats.failure_count == 0

    async def test_quality_validation(self):
        async with TrustLedger(":memory:") as ledger:
            with pytest.raises(ValueError, match="quality"):
                await ledger.record_outcome("agent-1", "code", True, 1.5, 1.0)

    async def test_duration_validation(self):
        async with TrustLedger(":memory:") as ledger:
            with pytest.raises(ValueError, match="duration"):
                await ledger.record_outcome("agent-1", "code", True, 0.5, -1.0)


# ═══════════════════════════════════════════════════════════════════════════
# EVOLUTION
# ═══════════════════════════════════════════════════════════════════════════


class TestEvolution:
    def _make_engine(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        return EvolutionEngine(db_path=tmp.name)

    def test_record_outcome(self):
        engine = self._make_engine()
        engine.record_outcome("del-1", success=True, quality_score=0.85)

    def test_evolve_strategies(self):
        engine = self._make_engine()
        engine.record_outcome(
            "del-1", success=True, quality_score=0.85,
            complexity=0.5, subtask_count=3,
            agent_ids=["agent-1"],
        )
        strategies = engine.evolve_strategies()
        assert "quality_trend" in strategies
        assert strategies["quality_trend"]["ema_quality"] > 0

    def test_quality_trend(self):
        engine = self._make_engine()
        for i in range(10):
            engine.record_outcome(
                f"del-{i}", success=True,
                quality_score=0.5 + i * 0.04,
            )
        strategies = engine.evolve_strategies()
        assert strategies["quality_trend"]["trend"] == "improving"

    def test_performance_trends_empty(self):
        engine = self._make_engine()
        trends = engine.get_performance_trends(30)
        assert trends["summary"]["total"] == 0

    def test_recommendations_normal(self):
        engine = self._make_engine()
        for i in range(10):
            engine.record_outcome(
                f"del-{i}", success=True, quality_score=0.8,
            )
        recs = engine.get_recommendations()
        assert len(recs) >= 1

    def test_get_weight_default(self):
        engine = self._make_engine()
        assert engine.get_weight("nonexistent", 42.0) == 42.0


# ═══════════════════════════════════════════════════════════════════════════
# EXECUTOR
# ═══════════════════════════════════════════════════════════════════════════


class TestExecutor:
    async def test_execute_with_handler(self):
        executor = SubtaskExecutor()

        async def mock_handler(name, args):
            return {"content": [{"type": "text", "text": "Found 5 papers"}]}

        executor.register_handler("search", mock_handler)
        result = await executor.execute("st-1", "search", "find AI papers")
        assert result.success is True
        assert "5 papers" in result.output

    async def test_execute_no_handler(self):
        executor = SubtaskExecutor()
        result = await executor.execute("st-1", "unknown", "anything")
        assert result.success is False
        assert "No handler" in result.error

    async def test_execute_handler_error(self):
        executor = SubtaskExecutor()

        async def failing_handler(name, args):
            raise RuntimeError("Connection failed")

        executor.register_handler("broken", failing_handler)
        result = await executor.execute("st-1", "broken", "try this")
        assert result.success is False
        assert "RuntimeError" in result.error

    async def test_execute_batch_parallel(self):
        executor = SubtaskExecutor()

        async def mock_handler(name, args):
            return "ok"

        executor.register_handler("agent-1", mock_handler)
        executor.register_handler("agent-2", mock_handler)

        subtasks = [
            {"subtask_id": "st-1", "agent_id": "agent-1", "description": "task 1"},
            {"subtask_id": "st-2", "agent_id": "agent-2", "description": "task 2"},
        ]
        results = await executor.execute_batch(subtasks, parallel=True)
        assert len(results) == 2
        assert all(r.success for r in results)

    async def test_execute_batch_sequential(self):
        executor = SubtaskExecutor()
        calls: list[str] = []

        async def tracking_handler(name, args):
            calls.append(name)
            return "done"

        executor.register_handler("a", tracking_handler)
        executor.register_handler("b", tracking_handler)

        subtasks = [
            {"subtask_id": "st-1", "agent_id": "a", "description": "first"},
            {"subtask_id": "st-2", "agent_id": "b", "description": "second"},
        ]
        results = await executor.execute_batch(subtasks, parallel=False)
        assert len(results) == 2
        assert calls == ["a", "b"]

    async def test_execution_result_to_dict(self):
        executor = SubtaskExecutor()

        async def mock_handler(name, args):
            return "result text"

        executor.register_handler("agent", mock_handler)
        result = await executor.execute("st-1", "agent", "test")
        d = result.to_dict()
        assert d["success"] is True
        assert d["subtask_id"] == "st-1"
        assert "timestamp" in d


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════


class TestIntegration:
    def test_classify_decompose_route(self):
        """Full pipeline: classify -> decompose -> route."""
        profile = classify_task("Build a REST API with authentication")
        subtasks = decompose_task("Build a REST API with authentication", profile)
        agents = [
            AgentCapability(
                agent_id="api::builder", name="builder",
                description="Build REST API endpoints and authentication",
                keywords=["build", "rest", "authentication", "endpoints"],
                estimated_cost=0.5,
            ),
        ]
        assignments = route_batch(subtasks, agents)
        assert len(assignments) == len(subtasks)

    def test_four_ds_pipeline(self):
        """Run all 4Ds gates on a task."""
        profile = TaskProfile(
            complexity=0.6, criticality=0.4, verifiability=0.7,
            reversibility=0.8, subjectivity=0.3,
        )
        approved, _ = delegation_gate("Implement search feature", profile)
        assert approved is True

        score, _ = description_gate(
            "Implement full-text search with query expansion that must return "
            "results in < 200ms and should support boolean operators"
        )
        assert score >= 0.5

        quality, issues = discernment_gate(
            "Search implementation with inverted index and boolean operators",
            "Full-text search with boolean operators",
            profile,
        )
        assert quality > 0.4

        safe, warnings = diligence_gate("Implement search feature", profile)
        assert safe is True

    async def test_trust_evolution_loop(self):
        """Trust ledger feeds evolution engine."""
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        engine = EvolutionEngine(db_path=tmp.name)

        async with TrustLedger(":memory:") as ledger:
            score = await ledger.record_outcome("agent-1", "search", True, 0.9, 2.0)
            assert score > 0.5

        engine.record_outcome("del-1", success=True, quality_score=0.9)
        strategies = engine.evolve_strategies()
        assert strategies["quality_trend"]["ema_quality"] > 0
