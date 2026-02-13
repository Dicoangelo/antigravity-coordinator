# PRD: Antigravity Coordinator — Self-Optimizing Agent Coordinator

## Overview

Package the existing multi-agent coordination infrastructure (`~/.claude/coordinator/`, DQ scoring engine, ACE consensus, pattern orchestrator) into a standalone, installable Python product that self-optimizes through research-driven feedback loops. The coordinator dynamically selects agent topologies, routes tasks to optimal model configurations, and continuously improves baselines from session outcomes.

This is the productization of Cluster 4 from a 64-paper research session, incorporating breakthroughs from Agyn (dynamic topology), W&D (parallel dispatch), EGSS (entropy-guided scaling), and Spectral Guardrails (safe constraints).

**Key differentiator:** No other coordination tool learns from its own execution history via DQ-scored adaptive consensus. This is the only self-optimizing coordinator on the market.

## Goals

- Package existing coordinator, DQ scorer, ACE engine, and pattern orchestrator as `antigravity-coordinator` (pip-installable)
- Provide CLI (`coord`) and FastAPI API for both interactive and programmatic use
- Implement entropy-guided compute allocation (EGSS) — spend tokens where uncertainty is highest
- Add dynamic agent topology selection (Agyn-inspired) — choose parallel vs sequential vs hybrid per-task
- Ship with self-optimization loop: Session → ACE → Pattern → Baseline Update → Better Future Routing
- Achieve ≥75% routing accuracy and ≥20% cost reduction vs random agent selection out of the box
- Target $20/$200/$2000 monthly pricing tiers (indie/team/enterprise)

## Quality Gates

These commands must pass for every user story:
- `pytest tests/ -x --tb=short` — All tests pass
- `mypy src/ --strict` — Type checking (strict mode)
- `ruff check src/` — Linting
- `ruff format --check src/` — Formatting

## User Stories

### US-001: Python Package Scaffolding
**Description:** As a developer, I want to install `antigravity-coordinator` via pip so that I can use the coordinator as a standalone tool.

**Acceptance Criteria:**
- [ ] Create `~/projects/products/antigravity-coordinator/` with `pyproject.toml` (hatchling build)
- [ ] Package name: `antigravity-coordinator`, import name: `coordinator`
- [ ] Source layout: `src/coordinator/` with `__init__.py`, `__version__ = "0.1.0"`
- [ ] Entry points: `coord = "coordinator.cli:main"` and `coord-api = "coordinator.api.server:main"`
- [ ] Dependencies: click, fastapi, uvicorn, sqlite-utils, rich (for TUI output)
- [ ] Dev dependencies: pytest, mypy, ruff, httpx (for testing)
- [ ] `uv pip install -e ".[dev]"` works without errors
- [ ] `coord --version` prints `0.1.0`

### US-002: Migrate Core Orchestration Engine
**Description:** As a developer, I want the coordinator's core orchestration logic packaged in the library so that agent spawning, registry, and conflict resolution work standalone.

**Acceptance Criteria:**
- [ ] Port `~/.claude/coordinator/orchestrator.py` → `src/coordinator/engine/orchestrator.py`
- [ ] Port `~/.claude/coordinator/registry.py` → `src/coordinator/engine/registry.py`
- [ ] Port `~/.claude/coordinator/distribution.py` → `src/coordinator/engine/distribution.py`
- [ ] Port `~/.claude/coordinator/conflict.py` → `src/coordinator/engine/conflict.py`
- [ ] Port `~/.claude/coordinator/executor.py` → `src/coordinator/engine/executor.py`
- [ ] Remove hardcoded paths — use `~/.coordinator/` as configurable data directory
- [ ] All imports resolve correctly from new package structure
- [ ] Unit tests for orchestrator, registry, conflict resolution pass

### US-003: Migrate Coordination Strategies
**Description:** As a user, I want to run `coord research|implement|review|full|team` so that I can coordinate agents with proven strategies.

**Acceptance Criteria:**
- [ ] Port `parallel_research.py` → `src/coordinator/strategies/research.py`
- [ ] Port `parallel_implement.py` → `src/coordinator/strategies/implement.py`
- [ ] Port `review_build.py` → `src/coordinator/strategies/review.py`
- [ ] Port `full_orchestration.py` → `src/coordinator/strategies/full.py`
- [ ] Add `team.py` strategy for Opus 4.6 agent teams
- [ ] Strategy registry: `STRATEGIES = {"research": ResearchStrategy, ...}`
- [ ] `coord research "task"` spawns 3 parallel explore agents
- [ ] `coord implement "task"` spawns N builders with file locks
- [ ] `coord status` shows active agents and their state

### US-004: Port DQ Scoring Engine to Python
**Description:** As a developer, I want the DQ scoring engine in Python (not Node.js) so that the entire package is single-language with no external runtime dependencies.

**Acceptance Criteria:**
- [ ] Create `src/coordinator/scoring/dq_scorer.py` — Python port of `dq-scorer.js`
- [ ] Create `src/coordinator/scoring/complexity_analyzer.py` — Python port of `complexity-analyzer.js`
- [ ] DQ formula: `score = validity * 0.35 + specificity * 0.25 + correctness * 0.40`
- [ ] Complexity analysis: token counting + signal detection (architecture, multiFile, code, analysis, creation, debug, simple)
- [ ] Historical learning from SQLite (replaces JSONL file reads)
- [ ] Port Opus 4.6 thinking tier selection (low/medium/high/max by complexity range)
- [ ] Baselines loaded from `~/.coordinator/baselines.json` with research lineage tracking
- [ ] `coordinator.scoring.score("Design a distributed system")` returns `{"model": "opus", "complexity": 0.85, "dq": 0.84}`
- [ ] Unit tests verify scoring matches known-good outputs from existing JS scorer

### US-005: Implement Entropy-Guided Compute Allocation (EGSS)
**Description:** As a user, I want the coordinator to spend more compute (tokens/agents) where uncertainty is highest so that hard subtasks get proportionally more resources.

**Acceptance Criteria:**
- [ ] Create `src/coordinator/optimization/entropy_allocator.py`
- [ ] Calculate per-subtask entropy from: DQ score variance, historical failure rate, complexity score
- [ ] Allocate compute budget: high-entropy tasks get more agents, more capable models, longer timeouts
- [ ] Low-entropy tasks get cheaper models and shorter timeouts
- [ ] Integration with strategy selection: `strategy.allocate(tasks, budget)` distributes resources
- [ ] Unit tests: given 5 tasks with known entropies, verify budget allocation is proportional

### US-006: Dynamic Agent Topology Selection (Agyn-inspired)
**Description:** As a user, I want the coordinator to automatically choose the best agent topology (parallel, sequential, hybrid, hierarchical) based on task characteristics.

**Acceptance Criteria:**
- [ ] Create `src/coordinator/optimization/topology_selector.py`
- [ ] Topologies: `parallel` (independent subtasks), `sequential` (dependent chain), `hybrid` (mix), `hierarchical` (supervisor + workers)
- [ ] Selection factors: task dependency graph, estimated complexity, available compute budget
- [ ] If all subtasks are independent → parallel topology
- [ ] If subtasks form a chain → sequential topology
- [ ] If subtasks have partial dependencies → hybrid topology
- [ ] If complexity > 0.9 → hierarchical with Opus supervisor
- [ ] `topology_selector.select(task_graph)` returns topology + agent assignments
- [ ] Unit tests for each topology selection path

### US-007: ACE Post-Session Analysis Integration
**Description:** As a user, I want every coordination session automatically analyzed by ACE so that the coordinator learns from successes and failures.

**Acceptance Criteria:**
- [ ] Create `src/coordinator/feedback/ace_analyzer.py`
- [ ] Port 6 ACE agents as analysis functions: outcome_detector, quality_scorer, complexity_analyzer, model_efficiency, productivity_analyzer, routing_quality
- [ ] Consensus synthesis: weighted DQ voting across all 6 agents
- [ ] Store session outcomes in `~/.coordinator/data/session-outcomes.db` (SQLite)
- [ ] Auto-trigger after every `coord` command completes
- [ ] `coord history` shows last 10 session outcomes with DQ scores
- [ ] Unit tests for consensus calculation with known agent outputs

### US-008: Self-Optimization Feedback Loop
**Description:** As a user, I want the coordinator to automatically improve its baselines when it has enough evidence so that routing accuracy improves over time.

**Acceptance Criteria:**
- [ ] Create `src/coordinator/feedback/optimizer.py`
- [ ] After 50+ sessions, calculate optimal complexity thresholds from outcome data
- [ ] Propose baseline updates when confidence > 75% (require 30-day observation window)
- [ ] Auto-apply updates that improve accuracy by >5% on holdout set
- [ ] Safety: rollback if any metric drops >10% after update
- [ ] Research lineage: each update records the evidence that triggered it
- [ ] `coord optimize --dry-run` shows proposed changes without applying
- [ ] `coord optimize --apply` applies validated improvements
- [ ] Unit tests for threshold calculation from synthetic session data

### US-009: Pattern Detection and Strategy Suggestion
**Description:** As a user, I want the coordinator to detect what kind of work I'm doing and suggest the optimal strategy so that I don't have to think about which strategy to use.

**Acceptance Criteria:**
- [ ] Create `src/coordinator/optimization/pattern_detector.py`
- [ ] Detect patterns: debugging, research, architecture, refactoring, implementation, testing, documentation, optimization
- [ ] Pattern → strategy mapping: debugging→review, research→research, architecture→full, refactoring→implement
- [ ] `coord auto "task description"` auto-selects strategy based on detected pattern
- [ ] Confidence threshold: >0.8 auto-selects, 0.5-0.8 suggests, <0.5 asks
- [ ] Log pattern detections for trend analysis
- [ ] Unit tests for pattern detection with known query strings

### US-010: FastAPI Server for Programmatic Access
**Description:** As an application developer, I want to access the coordinator via HTTP API so that I can integrate it into OS-App and other frontends.

**Acceptance Criteria:**
- [ ] Create `src/coordinator/api/server.py` with FastAPI app
- [ ] `POST /api/coordinate` — start a coordination session (accepts strategy, task, options)
- [ ] `GET /api/status` — get active agents and their state
- [ ] `GET /api/history` — get session outcomes with DQ scores
- [ ] `GET /api/health` — health check
- [ ] `GET /api/metrics` — routing accuracy, cost efficiency, DQ trends
- [ ] SSE endpoint `GET /api/stream` for real-time agent progress updates
- [ ] `coord-api --port 3848` starts the server
- [ ] Integration test: POST coordinate request, verify agents spawn, check status updates

### US-011: SQLite Storage Layer
**Description:** As a developer, I want all coordinator data in SQLite (WAL mode) so that reads and writes are concurrent, reliable, and queryable.

**Acceptance Criteria:**
- [ ] Create `src/coordinator/storage/database.py` with connection pooling
- [ ] Tables: `sessions`, `agents`, `outcomes`, `baselines`, `patterns`, `dq_scores`
- [ ] WAL mode enabled by default for concurrent access
- [ ] Migrations in `src/coordinator/storage/migrations/` with version tracking
- [ ] `coord init` creates `~/.coordinator/` directory and runs migrations
- [ ] `coord status` queries from SQLite (not JSON files)
- [ ] ON CONFLICT upserts (not INSERT OR REPLACE) to preserve data
- [ ] Unit tests for CRUD operations on each table

### US-012: Spectral Guardrails — Safety Constraints
**Description:** As a user, I want safety constraints on agent behavior so that agents can't exceed cost budgets, time limits, or scope boundaries.

**Acceptance Criteria:**
- [ ] Create `src/coordinator/safety/guardrails.py`
- [ ] Cost budget: configurable max spend per coordination session (default: no limit)
- [ ] Time limit: configurable max duration per agent (default: 300s, matches existing)
- [ ] Scope boundary: agents can only modify files matching specified glob patterns
- [ ] Heartbeat monitoring: kill agents that stop responding (60s timeout)
- [ ] Stale lock cleanup: automatically release locks held >5 minutes
- [ ] `coord config set max_cost 10.00` sets cost budget
- [ ] Guardrails are checked continuously, not just at start
- [ ] Unit tests for each guardrail trigger condition

## Functional Requirements

- FR-1: `coord init` must create `~/.coordinator/` with config, data directory, and SQLite database
- FR-2: `coord research "task"` must spawn 3 parallel explore agents and return their synthesized findings
- FR-3: `coord implement "task"` must spawn N builders with file locking to prevent write conflicts
- FR-4: `coord review "task"` must run builder + reviewer concurrently
- FR-5: `coord full "task"` must execute research → build → review pipeline sequentially
- FR-6: `coord team "task"` must spawn N Opus agents with peer coordination
- FR-7: `coord auto "task"` must detect pattern and select optimal strategy automatically
- FR-8: `coord status` must show all active agents, their state, and elapsed time
- FR-9: `coord history` must show last N session outcomes with DQ scores
- FR-10: `coord optimize --dry-run` must propose baseline improvements from session data
- FR-11: `coord-api` must start a FastAPI server on configurable port (default 3848)
- FR-12: All DQ scoring must use Python (no Node.js dependency)
- FR-13: All data must be stored in SQLite with WAL mode (no JSONL files)
- FR-14: Every coordination session must be automatically analyzed by ACE on completion
- FR-15: Baselines must track research lineage (which paper/evidence triggered each parameter)

## Non-Goals (Out of Scope)

- **No blockchain/token integration** — UCW handles that separately
- **No web dashboard** — Claude Command Center already provides this
- **No Claude Desktop/Code plugin** — CLI + API is the interface for v0.1
- **No cross-machine coordination** — single-machine only for v0.1
- **No custom agent definitions** — uses existing Claude Code subagent types
- **No GPU/ML training** — self-optimization uses statistical analysis, not neural networks
- **No authentication** — local-only tool, no auth needed for v0.1

## Technical Considerations

- **Port from JS to Python:** DQ scorer is currently Node.js (`dq-scorer.js`). Must port to Python for single-language package. Use existing test suite outputs as ground truth.
- **Subprocess management:** Agent spawning uses Claude Code's Task tool. The coordinator package wraps this with strategy logic, not reimplements it.
- **SQLite concurrency:** WAL mode + connection pooling. Use `ON CONFLICT` upserts (lesson from CCC dashboard SQLite fix).
- **Backwards compatibility:** Existing `coord` shell aliases should still work if the package is installed. Map existing commands to new CLI.
- **Config migration:** On first `coord init`, detect existing `~/.claude/coordinator/` data and offer to migrate.

## Success Metrics

- Package installs cleanly via `pip install antigravity-coordinator`
- `coord research "task"` completes in <5 minutes with useful synthesized output
- Routing accuracy ≥75% on first 50 sessions (matching existing system)
- Cost reduction ≥20% vs random model selection
- Self-optimization proposes first baseline update within 50 sessions
- All 12 user stories pass quality gates
- Zero data loss during migration from existing coordinator

## Open Questions

- Should v0.2 add MCP server mode (like UCW) for Claude Desktop integration?
- Should the API server be optional (separate `pip install antigravity-coordinator[api]`)?
- What's the migration path for the 3,039 existing DQ scores in `dq-scores.jsonl`?
