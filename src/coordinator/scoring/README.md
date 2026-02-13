# DQ Scoring Engine

Python implementation of the Decision Quality (DQ) scoring framework for intelligent LLM model routing.

## Overview

This module implements the ACE (Adaptive Convergence Engine) DQ Framework, ported from the JavaScript implementation at `~/.claude/kernel/dq-scorer.js`. It provides complexity analysis and model selection based on query characteristics.

## Key Features

- **Complexity Estimation**: Analyzes query complexity using Astraea-inspired signal detection
- **DQ Scoring**: Evaluates routing decisions using validity (35%) + specificity (25%) + correctness (40%)
- **Model Selection**: Automatically selects optimal model (haiku/sonnet/opus) based on complexity
- **Opus 4.6 Thinking Tiers**: Maps complexity to adaptive thinking effort levels (low/medium/high/max)
- **Cost Estimation**: Estimates API cost for each routing decision
- **Baselines**: Research-backed thresholds and parameters loaded from configuration

## Usage

### Basic Usage

```python
from coordinator.scoring import score

# Score a query
result = score("Design a distributed caching system")

print(f"Model: {result.model}")  # "opus"
print(f"Complexity: {result.complexity}")  # 0.75
print(f"DQ Score: {result.dq.score}")  # 0.82
print(f"Thinking Tier: {result.thinking_effort}")  # "medium"
print(f"Cost: ${result.cost_estimate:.6f}")  # $0.000125
```

### With Custom Baselines

```python
from pathlib import Path
from coordinator.scoring import score

baselines_path = Path("custom_baselines.json")
result = score("Fix typo in README", baselines_path)
```

### Complexity Analysis Only

```python
from coordinator.scoring import estimate_complexity

result = estimate_complexity("Refactor authentication module")
print(f"Score: {result.score}")  # 0.45
print(f"Model: {result.model}")  # "sonnet"
print(f"Reasoning: {result.reasoning}")  # "Medium query (60 tokens); code: 2 signal(s)"
```

### Advanced: Custom DQ Calculation

```python
from coordinator.scoring import calculate_dq
from coordinator.scoring.dq_scorer import load_baselines

baselines = load_baselines()
dq = calculate_dq(
    query="Architect microservices system",
    complexity=0.75,
    model="opus",
    baselines=baselines
)

print(f"Validity: {dq.components.validity}")  # 0.95
print(f"Specificity: {dq.components.specificity}")  # 0.88
print(f"Correctness: {dq.components.correctness}")  # 0.50
print(f"Overall: {dq.score}")  # 0.78
```

## API Reference

### `score(query: str, baselines_path: Path | None = None) -> ScoringResult`

Main entry point. Routes a query to the optimal model with full DQ scoring.

**Parameters:**
- `query`: Query string to analyze
- `baselines_path`: Optional path to custom baselines.json

**Returns:** `ScoringResult` with:
- `model`: Selected model (haiku/sonnet/opus)
- `complexity`: Complexity score (0-1)
- `dq`: DQ score with component breakdown
- `thinking_effort`: Opus 4.6 thinking tier (if applicable)
- `cost_estimate`: Estimated API cost in dollars
- `reasoning`: Human-readable complexity explanation
- `baseline_version`: Version of baselines used

### `estimate_complexity(query: str) -> ComplexityResult`

Analyze query complexity without DQ scoring.

**Returns:** `ComplexityResult` with:
- `score`: Complexity score (0-1)
- `tokens`: Estimated token count
- `signals`: Detected signal categories with counts
- `model`: Recommended model
- `reasoning`: Explanation of complexity assessment

### `calculate_dq(...) -> DQScore`

Calculate DQ score for a specific model choice.

**Parameters:**
- `query`: Query string
- `complexity`: Complexity score (0-1)
- `model`: Model to evaluate
- `baselines`: Baselines configuration
- `history`: Optional historical decisions (for correctness assessment)

**Returns:** `DQScore` with overall score and component breakdown

## Model Thresholds

From `default_baselines.json` (v1.1.0):

| Model | Complexity Range | Optimal Range | Use Cases |
|-------|------------------|---------------|-----------|
| Haiku | 0.0 - 0.20 | 0.0 - 0.15 | Simple Q&A, formatting, quick explanations |
| Sonnet | 0.15 - 0.70 | 0.20 - 0.60 | Code generation, analysis, moderate reasoning |
| Opus | 0.60 - 1.0 | 0.70 - 1.0 | Architecture, research, complex problem solving |

### Opus 4.6 Thinking Tiers

| Tier | Complexity Range | Use Cases |
|------|------------------|-----------|
| Low | 0.60 - 0.72 | Quick architecture, simple review |
| Medium | 0.72 - 0.85 | Multi-file refactor, debugging |
| High | 0.85 - 0.95 | Complex algorithms, system design |
| Max | 0.95 - 1.00 | Research synthesis, frontier problems |

## DQ Formula

```
DQ Score = (validity × 0.35) + (specificity × 0.25) + (correctness × 0.40)
```

**Components:**
- **Validity**: Does the model selection make logical sense given complexity?
- **Specificity**: How precise is the model selection?
- **Correctness**: Historical accuracy for similar queries (0.5 neutral without history)

## Signal Categories

Complexity analysis detects 7 signal categories:

| Category | Weight | Examples |
|----------|--------|----------|
| Architecture | +0.25 | design, system, pattern, microservice, distributed |
| Multi-file | +0.20 | across, all files, project-wide, refactor all |
| Code | +0.15 | function, class, async, interface, type |
| Analysis | +0.15 | analyze, review, audit, investigate |
| Creation | +0.10 | create, build, implement, develop |
| Debug | +0.10 | error, fix, bug, crash, exception |
| Simple | -0.15 | what is, how to, explain, hello, thanks |

## Research Lineage

Based on research from:

1. **arXiv:2512.14142** - Astraea: State-Aware LLM Scheduling Engine
   - Applied: 2026-01-18
   - Insight: Complexity thresholds for model selection

2. **arXiv:2511.15755** - MyAntFarm.ai: DQ Framework for Multi-Agent Systems
   - Applied: 2026-01-18
   - Insight: Decision Quality scoring formula (40/30/30 → 35/25/40)

3. **Implementation Feedback** - Haiku Threshold Tightening
   - Applied: 2026-01-30
   - Insight: Haiku 4.3% success rate → tightened range to 0.0-0.20

## Testing

Run tests with:

```bash
pytest tests/test_scoring.py -v
```

Key test scenarios:
- Simple queries → haiku
- Architecture queries → opus
- Debug/typo fixes → haiku
- Moderate refactoring → sonnet
- Complex architecture → sonnet/opus
- DQ components in 0-1 range
- Complexity scores in 0-1 range

## Type Safety

Fully typed with `mypy --strict` compliance:

```bash
mypy src/coordinator/scoring/ --strict
```

All functions have complete type annotations using `from __future__ import annotations`.

## Dependencies

- Python 3.11+
- No external dependencies (pure Python)
- Uses standard library: `json`, `re`, `dataclasses`, `pathlib`, `typing`

## File Structure

```
src/coordinator/scoring/
├── __init__.py                  # Public API exports
├── complexity_analyzer.py       # Complexity estimation engine
├── dq_scorer.py                 # DQ scoring and model selection
├── default_baselines.json       # Default configuration
└── README.md                    # This file
```

## Performance

- **Latency**: < 5ms per scoring decision (no I/O, pure computation)
- **Memory**: < 1MB for baselines and state
- **Accuracy**: 93.1% on validation test set (from baselines metadata)
- **Cost Reduction**: 72.9% vs random model selection

## Integration with Coordinator

This module is designed for standalone use but integrates with the coordinator database layer for:
- Historical correctness assessment (query similarity matching)
- Routing decision logging and learning
- Performance metrics tracking

The coordinator wraps the `score()` function and provides:
- Database-backed history for correctness scoring
- Persistent decision logging
- Feedback collection and learning loops
- Multi-agent strategy selection based on DQ scores

## Configuration

Baselines are loaded from `default_baselines.json` or a custom path. The configuration includes:

- **DQ Weights**: validity (0.35), specificity (0.25), correctness (0.40)
- **Complexity Thresholds**: per-model ranges and optimal zones
- **Cost per Million Tokens**: input/output pricing for each model
- **Thinking Tiers**: Opus 4.6 complexity-to-effort mapping
- **Research Lineage**: Papers and insights that informed the design

## Version History

- **1.1.0** (2026-02-05): Correctness weight boost (30% → 40%)
- **1.0.0** (2026-01-18): Initial implementation based on ACE framework

## License

Same as parent project.
