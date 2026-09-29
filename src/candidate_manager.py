"""Candidate lifecycle and filtering for SEMSYNTH Lite."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Iterable

from src.code_executor import CodeExecutor


@dataclass
class Candidate:
    code: str
    index: int
    score: float = 1.0
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def deactivate(self, reason: str = "") -> None:
        self.is_active = False
        self.metadata["deactivation_reason"] = reason


class CandidateManager:
    def __init__(self, executor: CodeExecutor | None = None):
        self.executor = executor or CodeExecutor()
        self._candidates: list[Candidate] = []
        self._history: list[dict[str, Any]] = []

    def add_candidates(self, code_list: list[str]) -> list[Candidate]:
        start = len(self._candidates)
        added = [Candidate(code=c, index=start + i) for i, c in enumerate(code_list)]
        self._candidates.extend(added)
        self._log_event("add_candidates", {"count": len(added)})
        return added

    def keep_indices(self, indices: Iterable[int], reason: str = "clarification") -> int:
        keep = set(indices)
        removed = 0
        for c in self.get_active():
            if c.index not in keep:
                c.deactivate(reason)
                removed += 1
        self._log_event("filter", {"keep": sorted(keep), "removed": removed, "reason": reason})
        return removed

    def filter_by_answer(
        self,
        question: str,
        answer: bool,
        test_input: dict[str, Any] | None = None,
        expected_outputs: dict[bool | str, Any] | None = None,
        function_name: str | None = None,
        yes_candidate_ids: Iterable[int] | None = None,
        no_candidate_ids: Iterable[int] | None = None,
    ) -> int:
        """Filter by an answer using an explicit candidate partition when available.

        The partition form is preferred because a Yes/No semantic property may map
        to several concrete outputs.  ``expected_outputs`` is retained for backward
        compatibility and is normalized for bool or 'yes'/'no' keys.
        """
        if yes_candidate_ids is not None and no_candidate_ids is not None:
            keep = yes_candidate_ids if answer else no_candidate_ids
            removed = self.keep_indices(keep, reason=f"answer={answer}: {question}")
        else:
            if expected_outputs is None or test_input is None or not function_name:
                raise ValueError("Need candidate partitions or function_name/test_input/expected_outputs")
            target = expected_outputs.get(answer)
            if target is None:
                target = expected_outputs.get("yes" if answer else "no")
            keep: list[int] = []
            for c in self.get_active():
                ok, value, _ = self.executor.execute_function(c.code, function_name, test_input)
                if ok and value == target:
                    keep.append(c.index)
            removed = self.keep_indices(keep, reason=f"answer={answer}: {question}")
        self._log_event("filter_by_answer", {"question": question, "answer": answer, "removed": removed})
        return removed

    def filter_by_test(self, function_name: str, test_input: dict[str, Any], expected_output: Any) -> int:
        keep: list[int] = []
        for c in self.get_active():
            ok, value, _ = self.executor.execute_function(c.code, function_name, test_input)
            if ok and value == expected_output:
                keep.append(c.index)
        removed = self.keep_indices(keep, reason="direct_test")
        self._log_event("filter_by_test", {"removed": removed})
        return removed

    def get_active(self) -> list[Candidate]:
        return [c for c in self._candidates if c.is_active]

    def get_best(self) -> Candidate | None:
        active = self.get_active()
        return max(active, key=lambda c: (c.score, -c.index)) if active else None

    @property
    def total_count(self) -> int:
        return len(self._candidates)

    @property
    def active_count(self) -> int:
        return len(self.get_active())

    @property
    def is_converged(self) -> bool:
        return self.active_count <= 1

    @property
    def history(self) -> list[dict[str, Any]]:
        return list(self._history)

    def _log_event(self, event_type: str, details: dict[str, Any]) -> None:
        self._history.append({"event": event_type, "active_after": self.active_count, "details": details})
