"""Tests for the coordinator CLI."""

from click.testing import CliRunner

from coordinator.cli import main


def test_version() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_init(tmp_path: object) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0
    assert "initialized" in result.output.lower()


def test_status() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0


def test_history() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["history"])
    assert result.exit_code == 0


def test_optimize_dry_run() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["optimize", "--dry-run"])
    assert result.exit_code == 0
