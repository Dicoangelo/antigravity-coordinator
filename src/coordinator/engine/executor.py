"""Agent Executor - Spawns and manages Claude agents."""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from coordinator.engine.conflict import ConflictManager
from coordinator.engine.registry import AgentRegistry, AgentState

# Use real binary path, not shell alias (aliases don't work in subprocess)
CLAUDE_REAL_BIN = os.environ.get("CLAUDE_REAL_BIN", str(Path.home() / ".local" / "bin" / "claude"))

# Maximum prompt length to prevent DoS via extremely long prompts
MAX_PROMPT_LENGTH = 50_000


@dataclass
class AgentConfig:
    """Configuration for an agent to spawn."""

    subtask: str
    prompt: str
    agent_type: str  # explore, general-purpose, Bash, Plan
    model: str = "sonnet"  # haiku, sonnet, opus
    timeout: int = 300  # seconds
    run_in_background: bool = True
    files_to_lock: list[str] | None = None
    lock_type: str = "read"
    dq_score: float = 0.5
    cost_estimate: float = 0.0

    def __post_init__(self) -> None:
        if self.files_to_lock is None:
            self.files_to_lock = []


@dataclass
class AgentResult:
    """Result from an agent execution."""

    agent_id: str
    success: bool
    output: str
    error: str | None = None
    duration_seconds: float = 0.0
    files_modified: list[str] | None = None

    def __post_init__(self) -> None:
        if self.files_modified is None:
            self.files_modified = []


class AgentExecutor:
    """
    Executes agents via CLI subprocess.

    Note: The Task tool is used natively within Claude Code sessions.
    This executor is for programmatic spawning from Python scripts.
    """

    # Model mapping
    MODEL_MAP = {
        "haiku": "claude-3-5-haiku-latest",
        "sonnet": "claude-sonnet-4-20250514",
        "opus": "claude-opus-4-6",
    }

    # Default timeouts by model (increased for complex tasks)
    DEFAULT_TIMEOUTS = {
        "haiku": 180,  # 3 min
        "sonnet": 600,  # 10 min
        "opus": 1200,  # 20 min (up from 15 — extended thinking needs headroom)
    }

    # Thinking effort timeout multipliers for Opus 4.6
    THINKING_EFFORT_MULTIPLIERS = {
        "low": 0.75,  # 15 min — fast decisions
        "medium": 1.0,  # 20 min — default
        "high": 1.5,  # 30 min — complex reasoning
        "max": 2.0,  # 40 min — frontier problems
    }

    def __init__(
        self,
        registry: AgentRegistry | None = None,
        conflict_mgr: ConflictManager | None = None,
        data_dir: Path | None = None,
    ) -> None:
        self.registry = registry or AgentRegistry(data_dir)
        self.conflict_mgr = conflict_mgr or ConflictManager(data_dir)
        self._active_processes: dict[str, subprocess.Popen[str]] = {}
        self._claude_bin = self._resolve_claude_binary()

    @staticmethod
    def _resolve_claude_binary() -> str:
        """Resolve and validate the Claude binary path."""
        bin_path = os.environ.get("CLAUDE_REAL_BIN", str(Path.home() / ".local" / "bin" / "claude"))
        resolved = Path(bin_path).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Claude binary not found: {resolved}")
        if not os.access(str(resolved), os.X_OK):
            raise PermissionError(f"Claude binary not executable: {resolved}")
        return str(resolved)

    def _validate_prompt(self, prompt: str) -> str:
        """Validate and sanitize prompt input."""
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        if len(prompt) > MAX_PROMPT_LENGTH:
            raise ValueError(f"Prompt exceeds maximum length ({MAX_PROMPT_LENGTH} chars)")
        # Strip null bytes and non-printable control chars (keep newlines, tabs)
        return "".join(c for c in prompt if c == "\n" or c == "\t" or (ord(c) >= 32))

    def spawn_cli_agent(self, config: AgentConfig, task_id: str) -> str:
        """
        Spawn an agent using Claude CLI.

        Args:
            config: Agent configuration
            task_id: Parent coordination task ID

        Returns:
            agent_id of the spawned agent
        """
        # Register agent
        agent_id = self.registry.register(
            task_id=task_id,
            subtask=config.subtask,
            agent_type=config.agent_type,
            model=config.model,
            files_to_lock=config.files_to_lock,
            dq_score=config.dq_score,
            cost_estimate=config.cost_estimate,
        )

        # Acquire file locks
        if config.files_to_lock:
            success, failed = self.conflict_mgr.acquire_batch(
                config.files_to_lock, agent_id, config.lock_type
            )
            if not success:
                self.registry.fail(agent_id, f"Could not acquire locks: {failed}")
                return agent_id

        # Build command
        model = self.MODEL_MAP.get(config.model, config.model)
        timeout = config.timeout or self.DEFAULT_TIMEOUTS.get(config.model, 300)

        safe_prompt = self._validate_prompt(config.prompt)
        cmd = [
            self._claude_bin,
            "--model",
            model,
            "--max-turns",
            "50",
            "-p",
            safe_prompt,
        ]

        # Mark as started
        self.registry.start(agent_id)

        try:
            # Run subprocess
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(Path.home()),
                check=False,
            )

            if result.returncode == 0:
                self.registry.complete(agent_id, {"output": result.stdout, "stderr": result.stderr})
            else:
                self.registry.fail(agent_id, result.stderr or "Non-zero exit code")

        except subprocess.TimeoutExpired:
            self.registry.timeout(agent_id)

        except Exception as e:
            self.registry.fail(agent_id, str(e))

        finally:
            # Release locks
            self.conflict_mgr.release_agent(agent_id)

        return agent_id

    def spawn_cli_agent_async(self, config: AgentConfig, task_id: str) -> str:
        """
        Spawn an agent asynchronously (non-blocking).

        Returns agent_id immediately, runs in background.
        """
        # Register agent
        agent_id = self.registry.register(
            task_id=task_id,
            subtask=config.subtask,
            agent_type=config.agent_type,
            model=config.model,
            files_to_lock=config.files_to_lock,
            dq_score=config.dq_score,
            cost_estimate=config.cost_estimate,
        )

        # Acquire file locks
        if config.files_to_lock:
            success, failed = self.conflict_mgr.acquire_batch(
                config.files_to_lock, agent_id, config.lock_type
            )
            if not success:
                self.registry.fail(agent_id, f"Could not acquire locks: {failed}")
                return agent_id

        # Build command
        model = self.MODEL_MAP.get(config.model, config.model)

        safe_prompt = self._validate_prompt(config.prompt)
        cmd = [
            self._claude_bin,
            "--model",
            model,
            "--max-turns",
            "50",
            "-p",
            safe_prompt,
        ]

        # Mark as started
        self.registry.start(agent_id)

        # Create output file for capturing
        output_file = Path(tempfile.gettempdir()) / f"claude-agent-{agent_id}.out"

        # Start subprocess
        with open(output_file, "w") as f:
            proc: subprocess.Popen[str] = subprocess.Popen(
                cmd, stdout=f, stderr=subprocess.STDOUT, cwd=str(Path.home()), text=True
            )

        self._active_processes[agent_id] = proc

        # Store output file path
        self.registry.heartbeat(agent_id, 0.1)

        return agent_id

    def spawn_parallel(
        self, configs: Sequence[AgentConfig], task_id: str, max_workers: int = 5
    ) -> list[str]:
        """
        Spawn multiple agents in parallel.

        Args:
            configs: List of agent configurations
            task_id: Parent coordination task ID
            max_workers: Maximum parallel agents

        Returns:
            List of agent_ids
        """
        agent_ids: list[str] = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.spawn_cli_agent, config, task_id): config for config in configs
            }

            for future in as_completed(futures):
                try:
                    agent_id = future.result()
                    agent_ids.append(agent_id)
                except Exception as e:
                    print(f"Agent spawn failed: {e}")

        return agent_ids

    def wait_for_agents(
        self, agent_ids: Sequence[str], timeout: int = 600
    ) -> dict[str, AgentResult]:
        """
        Wait for multiple agents to complete.

        Args:
            agent_ids: List of agent IDs to wait for
            timeout: Maximum wait time in seconds

        Returns:
            Dict mapping agent_id to AgentResult
        """
        results: dict[str, AgentResult] = {}
        start_time = time.time()

        while True:
            all_done = True

            for agent_id in agent_ids:
                if agent_id in results:
                    continue

                agent = self.registry.get(agent_id)
                if not agent:
                    results[agent_id] = AgentResult(
                        agent_id=agent_id, success=False, output="", error="Agent not found"
                    )
                    continue

                if agent.state in [
                    AgentState.COMPLETED.value,
                    AgentState.FAILED.value,
                    AgentState.TIMEOUT.value,
                    AgentState.CANCELLED.value,
                ]:
                    results[agent_id] = AgentResult(
                        agent_id=agent_id,
                        success=agent.state == AgentState.COMPLETED.value,
                        output=agent.result.get("output", "") if agent.result else "",
                        error=agent.error,
                    )
                else:
                    all_done = False

            if all_done:
                break

            if time.time() - start_time > timeout:
                # Mark remaining as timed out
                for agent_id in agent_ids:
                    if agent_id not in results:
                        self.registry.timeout(agent_id)
                        results[agent_id] = AgentResult(
                            agent_id=agent_id,
                            success=False,
                            output="",
                            error="Wait timeout exceeded",
                        )
                break

            time.sleep(1)  # Poll interval

        return results

    def cancel_agent(self, agent_id: str) -> None:
        """Cancel a running agent."""
        # Kill subprocess if tracked
        if agent_id in self._active_processes:
            proc = self._active_processes[agent_id]
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            del self._active_processes[agent_id]

        # Update registry
        self.registry.cancel(agent_id)

        # Release locks
        self.conflict_mgr.release_agent(agent_id)

    def cancel_task(self, task_id: str) -> None:
        """Cancel all agents for a coordination task."""
        agents = self.registry.get_task_agents(task_id)
        for agent in agents:
            if agent.state in [AgentState.PENDING.value, AgentState.RUNNING.value]:
                self.cancel_agent(agent.agent_id)

    def get_agent_output(self, agent_id: str) -> str | None:
        """Get output from an async agent."""
        output_file = Path(tempfile.gettempdir()) / f"claude-agent-{agent_id}.out"
        if output_file.exists():
            return output_file.read_text()
        return None


def generate_task_prompt(subtask: str, context: str = "", instructions: str = "") -> str:
    """
    Generate a prompt for an agent task.

    Args:
        subtask: The specific subtask to perform
        context: Additional context about the codebase
        instructions: Specific instructions for the agent

    Returns:
        Formatted prompt string
    """
    parts = [f"## Task\n{subtask}"]

    if context:
        parts.append(f"\n## Context\n{context}")

    if instructions:
        parts.append(f"\n## Instructions\n{instructions}")

    parts.append("\n## Output\nProvide a clear, structured response with your findings or changes.")

    return "\n".join(parts)


def generate_task_tool_config(config: AgentConfig) -> dict[str, Any]:
    """
    Generate configuration for the Task tool.

    This is used when calling the Task tool from within a Claude Code session.

    Returns:
        Dict with Task tool parameters
    """
    return {
        "description": config.subtask[:50],  # 3-5 word summary
        "prompt": config.prompt,
        "subagent_type": config.agent_type,
        "model": config.model,
        "run_in_background": config.run_in_background,
    }
