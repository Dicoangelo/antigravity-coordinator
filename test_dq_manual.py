#!/usr/bin/env python3
"""Manual test script for DQ scoring."""

from pathlib import Path

from coordinator.scoring import score

# Test cases
test_queries = [
    ("hello", "haiku"),
    ("Design a distributed caching system", "opus"),
    ("Fix the typo in README", "haiku"),
    ("Refactor authentication module to use dependency injection", "sonnet"),
    (
        "Architect a microservices system for real-time data processing at scale",
        "sonnet or opus",
    ),
]

print("DQ Scoring Test Results")
print("=" * 80)

baselines_path = Path(__file__).parent / "src/coordinator/scoring/default_baselines.json"

for query, expected in test_queries:
    result = score(query, baselines_path)

    print(f"\nQuery: {query}")
    print(f"Expected: {expected}")
    print(f"Got: {result.model}")
    print(f"Complexity: {result.complexity:.3f}")
    print(f"DQ Score: {result.dq.score:.3f}")
    print(
        f"DQ Components: V={result.dq.components.validity:.3f} "
        f"S={result.dq.components.specificity:.3f} "
        f"C={result.dq.components.correctness:.3f}"
    )
    print(f"Thinking Tier: {result.thinking_effort}")
    print(f"Cost Estimate: ${result.cost_estimate:.6f}")
    print(f"Reasoning: {result.reasoning}")

    # Check ranges
    assert 0.0 <= result.complexity <= 1.0, f"Complexity out of range: {result.complexity}"
    assert 0.0 <= result.dq.score <= 1.0, f"DQ score out of range: {result.dq.score}"
    assert (
        0.0 <= result.dq.components.validity <= 1.0
    ), f"Validity out of range: {result.dq.components.validity}"
    assert (
        0.0 <= result.dq.components.specificity <= 1.0
    ), f"Specificity out of range: {result.dq.components.specificity}"
    assert (
        0.0 <= result.dq.components.correctness <= 1.0
    ), f"Correctness out of range: {result.dq.components.correctness}"

    print("✓ All ranges valid")

print("\n" + "=" * 80)
print("All tests passed!")
