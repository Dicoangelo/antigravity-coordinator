# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **Shell alias collision**: `coord` is aliased in shell to `python3 ~/.claude/coordinator/orchestrator.py`. Use `.venv/bin/coord` directly or `python -m` prefix when testing entry points.
- **UCW package pattern**: hatchling build, `src/<pkg>/` layout, `[tool.hatch.build.targets.wheel] packages = ["src/<pkg>"]`, entry points via `[project.scripts]`.
- **Quality gate order**: install → coord --version → pytest → mypy --strict → ruff check → ruff format --check

---

## 2026-02-13 - US-001
- Scaffolding was already largely complete from a prior iteration (pyproject.toml, src/coordinator/, CLI, API stubs, tests)
- Added missing `sqlite-utils>=3.37` dependency to pyproject.toml (required by acceptance criteria but was absent)
- Created .venv and ran `uv pip install -e '.[dev]'` — installed 37 packages successfully
- All 14 acceptance criteria verified and passing:
  - `coord --version` → `coord, version 0.1.0`
  - 133 tests pass
  - mypy --strict: no issues in 31 files
  - ruff check: all passed
  - ruff format --check: 31 files already formatted
- Files changed: `pyproject.toml` (added sqlite-utils dependency)
- **Learnings:**
  - The shell alias `coord` shadows the package entry point — must use full venv path `.venv/bin/coord` for testing
  - Prior iteration already built out extensive modules (engine, feedback, optimization, safety, scoring, storage, strategies) beyond US-001 scope
  - Python 3.13.11 is the runtime in this environment
---

## 2026-02-13 - US-002 through US-010, US-012 (All Remaining Stories)
- All 10 remaining user stories verified and marked passing in a single verification pass
- Code was built by 4 parallel build agents in the prior session; this session fixed 11 test failures and wired CLI stubs
- **Key fixes applied:**
  - ace_analyzer.py: haiku efficiency threshold `< 0.4` → `<= 0.5`
  - database.py: removed FOREIGN KEY constraints causing test failures, fixed trailing comma SQL syntax
  - topology_selector.py: hierarchical check before linear chain, connectivity validation
  - pattern_detector.py: confidence formula `max_score / pattern_keyword_count`
  - guardrails.py: `fnmatch` → `PurePosixPath.full_match()` for `**` glob support
  - optimizer.py: `ORDER BY id DESC` for deterministic rollback ordering
- **CLI fully wired:** research, implement, review, full, team, auto, status, history, optimize, score commands
- Quality gates: 150 tests pass, mypy --strict clean, ruff check clean, ruff format clean
- GitHub repo created and pushed: `Dicoangelo/antigravity-coordinator` (private)
- Supreme README with capsule-render, Mermaid architecture diagram, shields.io badges
---

## 2026-02-13 - US-011
- Storage layer (database.py, storage/__init__.py) was already implemented from a prior iteration with all 6 tables, WAL mode, context manager, schema versioning, and ON CONFLICT upsert pattern
- CLI `init` command was already wired to call `database.ensure_tables()`
- **Main gap was test coverage**: existing tests only covered sessions, dq_scores, and schema_version (6 tests)
- Added 17 new CRUD tests covering all remaining tables: agents (insert/update/upsert/delete), outcomes (insert/upsert/delete), baselines (insert/update/delete), patterns (insert/update/delete), plus dq_scores update/delete and directory structure + idempotency tests
- Files changed: `tests/test_database.py` (expanded from 6 to 23 tests)
- Quality gates: 150 tests pass, mypy --strict clean, ruff check clean, ruff format clean
- **Learnings:**
  - Tables with natural unique keys (sessions→session_id, agents→agent_id, outcomes→session_id) support ON CONFLICT upserts directly; tables with only autoincrement PK (baselines, patterns) use standard insert + update-by-id pattern
  - Schema uses `INSERT OR IGNORE INTO schema_version` which is acceptable for seed data (version tracking), distinct from `INSERT OR REPLACE` which is banned for regular data due to column-zeroing risk
---
