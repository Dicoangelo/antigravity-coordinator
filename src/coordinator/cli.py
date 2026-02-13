"""CLI entry point for the Antigravity Coordinator."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click
from rich.console import Console
from rich.table import Table

from coordinator import __version__

if TYPE_CHECKING:
    from coordinator.engine.orchestrator import CoordinationResult, MultiAgentOrchestrator

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="coord")
def main() -> None:
    """Antigravity Coordinator — self-optimizing multi-agent coordination."""


@main.command()
def init() -> None:
    """Initialize coordinator: create ~/.coordinator/ and database."""
    from coordinator.storage.database import Database

    db = Database()
    db.ensure_tables()
    console.print(f"[green]Coordinator initialized at {db.data_dir}[/green]")
    console.print(f"  Database: {db.db_path}")
    console.print(f"  Config:   {db.data_dir / 'config.toml'}")


def _get_orchestrator() -> MultiAgentOrchestrator:  # noqa: F821
    from coordinator.engine.orchestrator import MultiAgentOrchestrator

    return MultiAgentOrchestrator()


@main.command()
@click.argument("task")
def research(task: str) -> None:
    """Run parallel research with 3 explore agents."""
    orch = _get_orchestrator()
    console.print(f"[bold cyan]Research:[/bold cyan] {task}")
    result = orch.coordinate(task, strategy="research", confirm_cost=False)
    _print_result(result)


@main.command()
@click.argument("task")
def implement(task: str) -> None:
    """Run parallel builders with file locks."""
    orch = _get_orchestrator()
    console.print(f"[bold cyan]Implement:[/bold cyan] {task}")
    result = orch.coordinate(task, strategy="implement", confirm_cost=False)
    _print_result(result)


@main.command()
@click.argument("task")
def review(task: str) -> None:
    """Run builder + reviewer concurrently."""
    orch = _get_orchestrator()
    console.print(f"[bold cyan]Review:[/bold cyan] {task}")
    result = orch.coordinate(task, strategy="review-build", confirm_cost=False)
    _print_result(result)


@main.command()
@click.argument("task")
def full(task: str) -> None:
    """Run research -> build -> review pipeline."""
    orch = _get_orchestrator()
    console.print(f"[bold cyan]Full pipeline:[/bold cyan] {task}")
    result = orch.coordinate(task, strategy="full", confirm_cost=False)
    _print_result(result)


@main.command()
@click.argument("task")
def team(task: str) -> None:
    """Run Opus 4.6 agent team (parallel, peer-coordinated)."""
    orch = _get_orchestrator()
    console.print(f"[bold cyan]Team:[/bold cyan] {task}")
    result = orch.coordinate(task, strategy="team", confirm_cost=False)
    _print_result(result)


@main.command()
@click.argument("task")
def auto(task: str) -> None:
    """Auto-detect pattern and select optimal strategy."""
    from coordinator.optimization.pattern_detector import PatternDetector
    from coordinator.scoring.dq_scorer import score as dq_score

    detector = PatternDetector()
    pattern = detector.detect(task)
    scoring = dq_score(task)

    console.print(f"[bold]Pattern:[/bold] {pattern.pattern} ({pattern.confidence:.0%} confidence)")
    console.print(f"[bold]Strategy:[/bold] {pattern.suggested_strategy}")
    console.print(
        f"[bold]DQ Score:[/bold] {scoring.dq.score:.3f} → {scoring.model} "
        f"(complexity: {scoring.complexity:.2f})"
    )

    if pattern.confidence >= 0.8:
        console.print(f"\n[green]Auto-selecting:[/green] {pattern.suggested_strategy}")
        orch = _get_orchestrator()
        result = orch.coordinate(task, strategy=pattern.suggested_strategy, confirm_cost=False)
        _print_result(result)
    elif pattern.confidence >= 0.5:
        console.print(f'\n[yellow]Suggested:[/yellow] coord {pattern.suggested_strategy} "{task}"')
    else:
        console.print("\n[dim]Low confidence — defaulting to implement strategy[/dim]")
        orch = _get_orchestrator()
        result = orch.coordinate(task, strategy="implement", confirm_cost=False)
        _print_result(result)


@main.command()
def status() -> None:
    """Show active agents and their state."""
    from coordinator.engine.registry import AgentRegistry

    registry = AgentRegistry()
    active = registry.get_active()

    if not active:
        console.print("[dim]No active agents.[/dim]")
        return

    table = Table(title="Active Agents")
    table.add_column("Agent ID", style="cyan")
    table.add_column("Task", max_width=40)
    table.add_column("Model", style="green")
    table.add_column("State", style="yellow")
    table.add_column("Progress")

    for agent in active:
        table.add_row(
            agent.agent_id,
            agent.subtask[:40],
            agent.model,
            agent.state,
            f"{agent.progress:.0%}",
        )

    console.print(table)
    stats = registry.get_stats()
    console.print(
        f"\nTotal: {stats['total_agents']} agents | "
        f"Active: {stats['active_count']} | "
        f"Cost: ${stats['total_cost_estimate']:.4f}"
    )


@main.command()
@click.option("--limit", default=20, help="Number of entries to show")
def history(limit: int) -> None:
    """Show recent session outcomes with DQ scores."""
    from coordinator.storage.database import Database

    db = Database()
    try:
        rows = db.execute("SELECT * FROM outcomes ORDER BY analyzed_at DESC LIMIT ?", (limit,))
    except Exception:
        console.print("[dim]No session history yet. Run a coordination task first.[/dim]")
        return

    if not rows:
        console.print("[dim]No session history yet. Run a coordination task first.[/dim]")
        return

    table = Table(title="Session History")
    table.add_column("Session", style="cyan")
    table.add_column("Outcome", style="green")
    table.add_column("Quality")
    table.add_column("Complexity")
    table.add_column("DQ Score", style="bold")
    table.add_column("Date")

    for row in rows:
        table.add_row(
            str(row["session_id"])[:16],
            str(row["outcome"]),
            f"{row['quality']:.1f}",
            f"{row['complexity']:.2f}",
            f"{row['dq_score']:.3f}",
            str(row["analyzed_at"])[:16],
        )

    console.print(table)


@main.command()
@click.option("--dry-run", is_flag=True, help="Show proposed changes without applying")
@click.option("--apply", "apply_changes", is_flag=True, help="Apply validated improvements")
def optimize(dry_run: bool, apply_changes: bool) -> None:
    """Propose or apply self-optimization baseline updates."""
    from coordinator.feedback.optimizer import Optimizer
    from coordinator.storage.database import Database

    db = Database()
    db.ensure_tables()
    optimizer = Optimizer(db)

    if dry_run:
        proposals = optimizer.propose()
        if not proposals:
            console.print("[dim]No optimization proposals yet. Need 50+ sessions.[/dim]")
            return

        table = Table(title="Proposed Optimizations")
        table.add_column("Parameter", style="cyan")
        table.add_column("Current")
        table.add_column("Proposed", style="green")
        table.add_column("Confidence")
        table.add_column("Improvement")
        table.add_column("Evidence")

        for p in proposals:
            table.add_row(
                p.parameter,
                f"{p.current_value:.3f}",
                f"{p.proposed_value:.3f}",
                f"{p.confidence:.0%}",
                f"+{p.improvement_pct:.1f}%",
                str(p.evidence_count),
            )

        console.print(table)

    elif apply_changes:
        proposals = optimizer.propose()
        if not proposals:
            console.print("[dim]No validated improvements to apply.[/dim]")
            return

        success = optimizer.apply(proposals)
        if success:
            console.print(f"[green]Applied {len(proposals)} optimization(s).[/green]")
        else:
            console.print("[red]Failed to apply optimizations.[/red]")

    else:
        console.print(
            "Use [bold]--dry-run[/bold] to see proposals or [bold]--apply[/bold] to apply them."
        )


@main.command()
@click.argument("query")
def score(query: str) -> None:
    """Score a query with DQ and show routing decision."""
    from coordinator.scoring.dq_scorer import score as dq_score

    result = dq_score(query)

    console.print(f"[bold]Query:[/bold] {result.query}")
    console.print(f"[bold]Complexity:[/bold] {result.complexity:.3f}")
    console.print(f"[bold]Model:[/bold] {result.model}")
    if result.thinking_effort:
        console.print(f"[bold]Thinking:[/bold] {result.thinking_effort}")
    console.print(
        f"[bold]DQ Score:[/bold] {result.dq.score:.3f} "
        f"(V:{result.dq.components.validity:.2f} "
        f"S:{result.dq.components.specificity:.2f} "
        f"C:{result.dq.components.correctness:.2f})"
    )
    console.print(f"[bold]Cost est:[/bold] ${result.cost_estimate:.6f}")
    console.print(f"[bold]Reasoning:[/bold] {result.reasoning}")


def _print_result(result: CoordinationResult) -> None:  # noqa: F821
    """Print coordination result summary."""
    status_color = {"success": "green", "partial": "yellow", "failed": "red"}.get(
        result.status, "dim"
    )

    console.print(f"\n[{status_color}]Status: {result.status}[/{status_color}]")
    console.print(f"Strategy: {result.strategy}")
    console.print(f"Duration: {result.duration_seconds:.1f}s")
    console.print(f"Agents: {len(result.agent_results)}")
    console.print(f"Cost: ${result.total_cost:.4f}")

    if result.synthesis.get("errors"):
        console.print("\n[red]Errors:[/red]")
        for err in result.synthesis["errors"]:
            console.print(f"  - {err}")
