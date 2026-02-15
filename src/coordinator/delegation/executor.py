"""
Subtask Executor — Dispatches Routed Subtasks to Callable Handlers

Takes subtasks that have been assigned to agents and executes them via
pluggable handler functions.

Usage:
    from coordinator.delegation.executor import SubtaskExecutor

    executor = SubtaskExecutor()
    executor.register_handler("search", my_search_handler)
    result = await executor.execute(subtask_id, "search", "find AI papers")
"""

import asyncio
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional

EXECUTION_TIMEOUT = 30.0

# Type alias for async handler: (tool_name, args) -> result
HandlerFn = Callable[[str, Dict[str, Any]], Coroutine[Any, Any, Any]]


class ExecutionResult:
    """Result of a subtask execution."""

    __slots__ = (
        "subtask_id",
        "agent_id",
        "success",
        "output",
        "error",
        "duration",
        "timestamp",
    )

    def __init__(
        self,
        subtask_id: str,
        agent_id: str,
        success: bool,
        output: str = "",
        error: str = "",
        duration: float = 0.0,
    ) -> None:
        self.subtask_id = subtask_id
        self.agent_id = agent_id
        self.success = success
        self.output = output
        self.error = error
        self.duration = duration
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subtask_id": self.subtask_id,
            "agent_id": self.agent_id,
            "success": self.success,
            "output": self.output[:500],
            "error": self.error,
            "duration": self.duration,
            "timestamp": self.timestamp,
        }


class SubtaskExecutor:
    """
    Executes routed subtasks by dispatching to registered async handlers.

    Unlike the ResearchGravity version which uses importlib to load MCP tool
    modules dynamically, this version uses explicit handler registration,
    making it fully standalone and testable.
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, HandlerFn] = {}

    def register_handler(self, agent_id: str, handler: HandlerFn) -> None:
        """Register an async handler for an agent_id."""
        self._handlers[agent_id] = handler

    async def execute(
        self,
        subtask_id: str,
        agent_id: str,
        description: str,
        chain_id: str = "",
    ) -> ExecutionResult:
        """Execute a single subtask."""
        start = time.time()

        handler = self._handlers.get(agent_id)
        if handler is None:
            return ExecutionResult(
                subtask_id=subtask_id,
                agent_id=agent_id,
                success=False,
                error=f"No handler registered for agent '{agent_id}'",
                duration=time.time() - start,
            )

        try:
            raw_result = await asyncio.wait_for(
                handler(agent_id, {"query": description}),
                timeout=EXECUTION_TIMEOUT,
            )

            output = self._extract_output(raw_result)
            is_error = self._is_error_result(raw_result)

            return ExecutionResult(
                subtask_id=subtask_id,
                agent_id=agent_id,
                success=not is_error,
                output=output,
                error="" if not is_error else output,
                duration=time.time() - start,
            )
        except asyncio.TimeoutError:
            return ExecutionResult(
                subtask_id=subtask_id,
                agent_id=agent_id,
                success=False,
                error=f"Execution timed out after {EXECUTION_TIMEOUT}s",
                duration=time.time() - start,
            )
        except Exception as exc:
            return ExecutionResult(
                subtask_id=subtask_id,
                agent_id=agent_id,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                duration=time.time() - start,
            )

    async def execute_batch(
        self,
        subtasks: List[Dict[str, str]],
        chain_id: str = "",
        parallel: bool = True,
    ) -> List[ExecutionResult]:
        """Execute multiple subtasks, optionally in parallel."""
        if parallel:
            tasks = [
                self.execute(
                    st["subtask_id"],
                    st["agent_id"],
                    st["description"],
                    chain_id,
                )
                for st in subtasks
            ]
            return list(await asyncio.gather(*tasks))
        else:
            results: list[ExecutionResult] = []
            for st in subtasks:
                result = await self.execute(
                    st["subtask_id"],
                    st["agent_id"],
                    st["description"],
                    chain_id,
                )
                results.append(result)
            return results

    @staticmethod
    def _extract_output(result: Any) -> str:
        if isinstance(result, str):
            return result

        if isinstance(result, dict):
            content = result.get("content", [])
            if isinstance(content, list):
                texts = []
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        texts.append(item["text"])
                if texts:
                    return "\n".join(texts)

            if "result" in result:
                return str(result["result"])

            import json

            return json.dumps(result, default=str)[:1000]

        return str(result)[:1000]

    @staticmethod
    def _is_error_result(result: Any) -> bool:
        if isinstance(result, dict):
            return bool(result.get("isError", False))
        return False
