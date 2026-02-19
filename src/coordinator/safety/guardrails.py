"""Safety guardrails for coordinator execution."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class GuardrailResult:
    """Result of a guardrail check."""

    passed: bool
    violation: str | None = None
    action: str = "continue"  # continue/warn/kill


class Guardrails:
    """Safety guardrails for coordinator execution."""

    def __init__(
        self,
        max_cost: float | None = None,
        max_duration: int = 300,
        allowed_globs: list[str] | None = None,
        heartbeat_timeout: int = 60,
    ) -> None:
        """Initialize guardrails.

        Args:
            max_cost: Maximum cost allowed (None = no limit)
            max_duration: Maximum duration in seconds (default: 300)
            allowed_globs: List of allowed file path globs (None = all allowed)
            heartbeat_timeout: Heartbeat timeout in seconds (default: 60)
        """
        self.max_cost = max_cost
        self.max_duration = max_duration
        self.allowed_globs = allowed_globs
        self.heartbeat_timeout = heartbeat_timeout

    def check_cost(self, current_cost: float) -> GuardrailResult:
        """Check if current cost exceeds limit.

        Args:
            current_cost: Current accumulated cost

        Returns:
            Guardrail check result
        """
        if self.max_cost is None:
            return GuardrailResult(passed=True)

        if current_cost > self.max_cost:
            return GuardrailResult(
                passed=False,
                violation=f"Cost limit exceeded: {current_cost:.2f} > {self.max_cost:.2f}",
                action="kill",
            )

        # Warn at 80% threshold
        if current_cost >= self.max_cost * 0.8:
            return GuardrailResult(
                passed=True,
                violation=f"Cost approaching limit: {current_cost:.2f} / {self.max_cost:.2f}",
                action="warn",
            )

        return GuardrailResult(passed=True)

    def check_duration(self, elapsed_seconds: int) -> GuardrailResult:
        """Check if elapsed time exceeds duration limit.

        Args:
            elapsed_seconds: Elapsed time in seconds

        Returns:
            Guardrail check result
        """
        if elapsed_seconds > self.max_duration:
            return GuardrailResult(
                passed=False,
                violation=f"Duration limit exceeded: {elapsed_seconds}s > {self.max_duration}s",
                action="kill",
            )

        # Warn at 80% threshold
        if elapsed_seconds >= self.max_duration * 0.8:
            return GuardrailResult(
                passed=True,
                violation=f"Duration approaching limit: {elapsed_seconds}s / {self.max_duration}s",
                action="warn",
            )

        return GuardrailResult(passed=True)

    def check_scope(self, file_path: str) -> GuardrailResult:
        """Check if file path is within allowed scope.

        Args:
            file_path: File path to check

        Returns:
            Guardrail check result
        """
        if self.allowed_globs is None:
            return GuardrailResult(passed=True)

        # Check if path matches any allowed glob (supports **)
        for pattern in self.allowed_globs:
            if self._glob_match(file_path, pattern):
                return GuardrailResult(passed=True)

        return GuardrailResult(
            passed=False,
            violation=f"File path outside allowed scope: {file_path}",
            action="kill",
        )

    @staticmethod
    def _glob_match(path: str, pattern: str) -> bool:
        """Match a file path against a glob pattern with ** support."""
        i, regex = 0, ""
        while i < len(pattern):
            if pattern[i:i + 3] == "**/":
                regex += "(?:[^/]+/)*"
                i += 3
            elif pattern[i:i + 2] == "**":
                regex += ".*"
                i += 2
            elif pattern[i] == "*":
                regex += "[^/]*"
                i += 1
            elif pattern[i] == "?":
                regex += "[^/]"
                i += 1
            elif pattern[i] in r".+^${}|()\[]":
                regex += "\\" + pattern[i]
                i += 1
            else:
                regex += pattern[i]
                i += 1
        return bool(re.fullmatch(regex, path))

    def check_heartbeat(self, last_heartbeat: float, now: float) -> GuardrailResult:
        """Check if heartbeat is within timeout.

        Args:
            last_heartbeat: Timestamp of last heartbeat
            now: Current timestamp

        Returns:
            Guardrail check result
        """
        elapsed = now - last_heartbeat

        if elapsed > self.heartbeat_timeout:
            return GuardrailResult(
                passed=False,
                violation=f"Heartbeat timeout: {elapsed:.0f}s since last heartbeat",
                action="kill",
            )

        # Warn at 80% threshold
        if elapsed >= self.heartbeat_timeout * 0.8:
            return GuardrailResult(
                passed=True,
                violation=(
                    f"Heartbeat approaching timeout: {elapsed:.0f}s / {self.heartbeat_timeout}s"
                ),
                action="warn",
            )

        return GuardrailResult(passed=True)

    def check_all(
        self,
        current_cost: float,
        elapsed_seconds: int,
        file_path: str | None,
        last_heartbeat: float,
        now: float,
    ) -> list[GuardrailResult]:
        """Run all guardrail checks.

        Args:
            current_cost: Current accumulated cost
            elapsed_seconds: Elapsed time in seconds
            file_path: File path to check (None to skip scope check)
            last_heartbeat: Timestamp of last heartbeat
            now: Current timestamp

        Returns:
            List of all guardrail check results
        """
        results = [
            self.check_cost(current_cost),
            self.check_duration(elapsed_seconds),
            self.check_heartbeat(last_heartbeat, now),
        ]

        if file_path is not None:
            results.append(self.check_scope(file_path))

        return results
