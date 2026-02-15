"""
4Ds Framework — Anthropic's Responsible AI Delegation Gates

Implements Anthropic's 4Ds framework for human-AI collaboration:
- Delegation: What tasks should be delegated to AI?
- Description: How well are task requirements communicated?
- Discernment: How do we evaluate AI outputs?
- Diligence: What ethical/safety constraints apply?

Each gate returns a tuple with decision and reasoning.
All evaluations are stored as DelegationEvent entries with gate_type field.
"""

import hashlib
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

from .models import TaskProfile


class FourDsGate:
    """Anthropic's 4Ds Framework gates for responsible AI delegation."""

    def __init__(self, db_path: str = "") -> None:
        if not db_path:
            db_path = str(
                Path.home() / ".agent-core" / "storage" / "delegation_events.db"
            )
        self.db_path = db_path

    # ── GATE 1: DELEGATION ───────────────────────────────────────────────

    def delegation_gate(
        self, task: str, profile: TaskProfile
    ) -> Tuple[bool, str]:
        """Gate 1: Should this task be delegated to AI?"""
        high_risk = (
            profile.subjectivity > 0.7
            and profile.criticality > 0.8
            and profile.reversibility < 0.2
        )

        if high_risk:
            reason = (
                f"Task blocked: high subjectivity ({profile.subjectivity:.2f}) + "
                f"high criticality ({profile.criticality:.2f}) + "
                f"low reversibility ({profile.reversibility:.2f}) requires human judgment"
            )
            self._log_event(
                task_id=self._hash_task(task),
                event_type="delegation_gate",
                status="blocked",
                details={"gate": "delegation", "approved": False, "reason": reason},
            )
            return False, reason

        if profile.criticality >= 0.8 and (
            profile.verifiability < 0.3 or profile.reversibility < 0.3
        ):
            if profile.verifiability < 0.3:
                reason = (
                    f"Task blocked: high criticality ({profile.criticality:.2f}) + "
                    f"low verifiability ({profile.verifiability:.2f}) makes validation difficult"
                )
            else:
                reason = (
                    f"Task blocked: high criticality ({profile.criticality:.2f}) + "
                    f"low reversibility ({profile.reversibility:.2f}) makes errors costly"
                )
            self._log_event(
                task_id=self._hash_task(task),
                event_type="delegation_gate",
                status="blocked",
                details={"gate": "delegation", "approved": False, "reason": reason},
            )
            return False, reason

        reason = "Task approved: risk factors within acceptable bounds"
        self._log_event(
            task_id=self._hash_task(task),
            event_type="delegation_gate",
            status="approved",
            details={"gate": "delegation", "approved": True, "reason": reason},
        )
        return True, reason

    # ── GATE 2: DESCRIPTION ──────────────────────────────────────────────

    def description_gate(self, task_description: str) -> Tuple[float, str]:
        """Gate 2: How well is this task described?"""
        score, suggestions = self._heuristic_description_score(task_description)
        self._log_event(
            task_id=self._hash_task(task_description),
            event_type="description_gate",
            status="analyzed",
            details={
                "gate": "description",
                "score": score,
                "suggestions": suggestions,
                "method": "heuristic",
            },
        )
        return score, suggestions

    def _heuristic_description_score(self, description: str) -> Tuple[float, str]:
        suggestions: list[str] = []
        scores: list[float] = []

        vague_words = [
            "thing", "stuff", "something", "somehow", "figure out",
            "handle", "deal with",
        ]
        has_vague = any(word in description.lower() for word in vague_words)

        specific_indicators = [
            "implement", "create", "build", "analyze", "verify", "test",
        ]
        has_specific = any(word in description.lower() for word in specific_indicators)

        specificity = 0.3 if has_vague else (0.8 if has_specific else 0.5)
        scores.append(specificity * 0.4)

        if has_vague:
            suggestions.append("Replace vague language with specific requirements")
        if not has_specific:
            suggestions.append("Add concrete action verbs (implement, create, analyze)")

        word_count = len(description.split())
        if word_count < 5:
            completeness = 0.2
            suggestions.append("Provide more context and details")
        elif word_count < 15:
            completeness = 0.5
            suggestions.append("Add more context about requirements and constraints")
        else:
            completeness = 0.8
        scores.append(completeness * 0.3)

        has_criteria = any(
            word in description.lower()
            for word in [
                "should", "must", "verify", "test", "expect",
                "ensure", "include", "output",
            ]
        )
        has_metrics = any(char in description for char in ["<", ">", "=", "%"]) or any(
            word in description.lower()
            for word in ["at least", "minimum", "maximum"]
        )

        constraint_clarity = (
            0.8 if (has_criteria and has_metrics) else (0.6 if has_criteria else 0.3)
        )
        scores.append(constraint_clarity * 0.3)

        if not has_criteria:
            suggestions.append("Define success criteria")
        if not has_metrics:
            suggestions.append("Add measurable constraints where applicable")

        total_score = max(0.0, min(1.0, sum(scores)))

        if total_score >= 0.8:
            suggestion_text = "Description is clear and complete"
        elif total_score >= 0.6:
            suggestion_text = "Good description. Consider: " + "; ".join(suggestions)
        else:
            suggestion_text = "Improve description: " + "; ".join(suggestions)

        return total_score, suggestion_text

    # ── GATE 3: DISCERNMENT ──────────────────────────────────────────────

    def discernment_gate(
        self, output: str, expected: str, profile: TaskProfile
    ) -> Tuple[float, List[str]]:
        """Gate 3: Is this AI output acceptable?"""
        issues: list[str] = []
        scores: list[float] = []

        output_words = set(output.lower().split())
        expected_words = set(expected.lower().split())
        keyword_overlap = len(output_words & expected_words) / max(
            len(expected_words), 1
        )
        completeness = min(1.0, keyword_overlap + 0.3)
        scores.append(completeness * 0.4)
        if completeness < 0.5:
            issues.append(
                f"Low completeness ({completeness:.2f}): output may be missing key requirements"
            )

        error_indicators = [
            "error", "failed", "exception", "undefined", "null", "nan", "invalid",
        ]
        has_errors = any(indicator in output.lower() for indicator in error_indicators)
        correctness = 0.3 if has_errors else 0.8
        scores.append(correctness * 0.3)
        if has_errors:
            issues.append("Output contains error indicators")

        length_ratio = len(output) / max(len(expected), 1)
        if length_ratio < 0.3:
            consistency = 0.4
            issues.append("Output significantly shorter than expected")
        elif length_ratio > 3.0:
            consistency = 0.6
            issues.append("Output significantly longer than expected")
        else:
            consistency = 0.8
        scores.append(consistency * 0.3)

        total_score = max(0.0, min(1.0, sum(scores)))

        if total_score < 0.7:
            issues.insert(
                0,
                f"Quality score {total_score:.2f} < 0.7 threshold — flagged for human review",
            )

        if not issues:
            issues.append("Output quality acceptable")

        self._log_event(
            task_id=self._hash_task(output[:100]),
            event_type="discernment_gate",
            status="reviewed" if total_score >= 0.7 else "flagged",
            details={
                "gate": "discernment",
                "quality_score": total_score,
                "issues": issues,
            },
        )

        return total_score, issues

    # ── GATE 4: DILIGENCE ────────────────────────────────────────────────

    def diligence_gate(
        self, task: str, profile: TaskProfile
    ) -> Tuple[bool, List[str]]:
        """Gate 4: Are ethical and safety constraints satisfied?"""
        warnings: list[str] = []

        sensitive_keywords = [
            "password", "credential", "secret", "api_key", "token",
            "private_key", "ssn", "credit_card", "personal", "pii",
            "confidential",
        ]
        has_sensitive_data = any(
            keyword in task.lower() for keyword in sensitive_keywords
        )
        if has_sensitive_data:
            warnings.append(
                "Task involves sensitive data — ensure proper access controls"
            )

        destructive_keywords = [
            "delete", "drop", "remove", "destroy", "wipe", "erase",
            "truncate", "clear", "purge", "reset",
        ]
        is_destructive = any(
            keyword in task.lower() for keyword in destructive_keywords
        )
        if is_destructive and profile.reversibility < 0.5:
            warnings.append(
                f"Destructive operation with low reversibility ({profile.reversibility:.2f}) — high risk"
            )

        if profile.criticality > 0.8 and profile.reversibility < 0.3:
            warnings.append(
                f"High criticality ({profile.criticality:.2f}) + "
                f"low reversibility ({profile.reversibility:.2f}) — consider human oversight"
            )

        production_keywords = [
            "deploy", "production", "release", "publish", "launch",
        ]
        is_production = any(
            keyword in task.lower() for keyword in production_keywords
        )
        if is_production and profile.verifiability <= 0.6:
            warnings.append(
                f"Production deployment with low verifiability ({profile.verifiability:.2f}) — "
                "ensure thorough testing"
            )

        unsafe = (
            has_sensitive_data and is_destructive and profile.reversibility < 0.2
        ) or (is_destructive and profile.reversibility < 0.15)

        if unsafe:
            if has_sensitive_data:
                warnings.insert(
                    0,
                    "BLOCKED: Sensitive + destructive + irreversible combination",
                )
            else:
                warnings.insert(
                    0,
                    "BLOCKED: Destructive operation with critically low reversibility",
                )
            safe = False
        else:
            safe = True
            if not warnings:
                warnings.append("No ethical or safety concerns detected")

        self._log_event(
            task_id=self._hash_task(task),
            event_type="diligence_gate",
            status="blocked" if not safe else ("warning" if len(warnings) > 1 else "safe"),
            details={
                "gate": "diligence",
                "safe": safe,
                "warnings": warnings,
            },
        )

        return safe, warnings

    # ── HELPERS ───────────────────────────────────────────────────────────

    @staticmethod
    def _hash_task(task: str) -> str:
        return hashlib.md5(task.encode()).hexdigest()[:8]

    def _log_event(
        self,
        task_id: str,
        event_type: str,
        status: str,
        details: dict[str, object],
    ) -> None:
        try:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.db_path, timeout=1.0)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS delegation_events (
                    event_id TEXT PRIMARY KEY,
                    delegation_id TEXT,
                    timestamp REAL,
                    event_type TEXT,
                    agent_id TEXT,
                    task_id TEXT,
                    status TEXT,
                    gate_type TEXT,
                    details TEXT
                )
            """)
            conn.execute(
                """INSERT INTO delegation_events (
                    event_id, delegation_id, timestamp, event_type,
                    agent_id, task_id, status, gate_type, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    uuid.uuid4().hex[:8],
                    "4ds-gate",
                    time.time(),
                    event_type,
                    "4ds-gate-system",
                    task_id,
                    status,
                    details.get("gate", ""),
                    json.dumps(details),
                ),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass  # Never block delegation on logging failure


# ── PUBLIC API ────────────────────────────────────────────────────────────


def delegation_gate(task: str, profile: TaskProfile) -> Tuple[bool, str]:
    """Gate 1: Is this task appropriate for AI delegation?"""
    return FourDsGate().delegation_gate(task, profile)


def description_gate(task_description: str) -> Tuple[float, str]:
    """Gate 2: How well is this task described?"""
    return FourDsGate().description_gate(task_description)


def discernment_gate(
    output: str, expected: str, profile: TaskProfile
) -> Tuple[float, List[str]]:
    """Gate 3: Is this AI output acceptable?"""
    return FourDsGate().discernment_gate(output, expected, profile)


def diligence_gate(task: str, profile: TaskProfile) -> Tuple[bool, List[str]]:
    """Gate 4: Are ethical and safety constraints satisfied?"""
    return FourDsGate().diligence_gate(task, profile)
