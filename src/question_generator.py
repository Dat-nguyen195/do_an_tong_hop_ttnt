"""Behavioral disagreement search and balanced Yes/No question selection."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from itertools import product
from typing import Any

from src.candidate_manager import Candidate
from src.code_executor import CodeExecutor


def _freeze(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    except TypeError:
        return repr(value)


@dataclass
class ClarificationQuestion:
    question: str
    test_input: dict[str, Any]
    yes_candidate_ids: list[int]
    no_candidate_ids: list[int]
    yes_output: Any
    no_outputs: list[Any] = field(default_factory=list)
    info_gain: float = 0.0
    balance: float = 0.0

    @property
    def expected_outputs(self) -> dict[str, Any]:
        return {"yes": self.yes_output, "no": self.no_outputs[0] if len(self.no_outputs) == 1 else self.no_outputs}


class QuestionGenerator:
    def __init__(self, executor: CodeExecutor | None = None, max_questions: int = 5, max_probe_inputs: int = 12):
        self.executor = executor or CodeExecutor()
        self.max_questions = max_questions
        self.max_probe_inputs = max_probe_inputs
        self._questions_asked: list[ClarificationQuestion] = []

    @staticmethod
    def _mutations(value: Any) -> list[Any]:
        values = [value]
        if isinstance(value, bool):
            values += [not value]
        elif isinstance(value, int) and not isinstance(value, bool):
            values += [0, 1, -1, value + 1]
        elif isinstance(value, float):
            values += [0.0, 1.0, value / 2]
        elif isinstance(value, str):
            values += ["", value[:1], value.upper(), value + value[:1]]
        elif isinstance(value, list):
            values += [[], value[:1], list(reversed(value))]
            if value:
                values += [value + [value[0]]]
                try:
                    values += [sorted(value)]
                except TypeError:
                    pass
        dedup = []
        seen = set()
        for item in values:
            key = _freeze(item)
            if key not in seen:
                seen.add(key)
                dedup.append(item)
        return dedup[:5]

    def build_probe_inputs(self, seed_inputs: list[dict[str, Any]] | None, params: str = "") -> list[dict[str, Any]]:
        seeds = list(seed_inputs or [])
        if not seeds:
            names = [p.strip() for p in params.split(",") if p.strip()]
            default: dict[str, Any] = {}
            for name in names:
                n = name.lower()
                if (
                    any(t in n for t in ("list", "nums", "numbers", "array", "arr", "items", "values"))
                    or n in {"xs", "ys", "test_tup1", "test_tup2", "tup1", "tup2"}
                    or "tuple" in n or "tup" in n
                ):
                    default[name] = [2, 1, 2]
                elif (
                    any(t in n for t in ("string", "str", "text", "word", "pattern", "prefix", "suffix"))
                    or n in {"s", "ch", "char", "sub_str"}
                ):
                    default[name] = "aba"
                elif n in {"n", "k", "x", "y", "threshold", "limit", "count", "size"}:
                    default[name] = 2
                else:
                    default[name] = 1
            if default:
                seeds = [default]
        probes: list[dict[str, Any]] = []
        seen = set()
        for seed in seeds:
            choices = [self._mutations(v) for v in seed.values()]
            keys = list(seed.keys())
            for combo in product(*choices):
                item = dict(zip(keys, combo))
                key = _freeze(item)
                if key not in seen:
                    seen.add(key)
                    probes.append(item)
                if len(probes) >= self.max_probe_inputs:
                    return probes
        return probes

    def _partition(self, candidates: list[Candidate], function_name: str, test_input: dict[str, Any]):
        groups: dict[str, dict[str, Any]] = {}
        for c in candidates:
            ok, value, error = self.executor.execute_function(c.code, function_name, test_input)
            observed = value if ok else {"__error__": error}
            key = _freeze(observed)
            groups.setdefault(key, {"value": observed, "ids": []})["ids"].append(c.index)
            c.metadata.setdefault("behavior_signature", {})[_freeze(test_input)] = observed
        return list(groups.values())

    @staticmethod
    def _binary_score(n_total: int, yes_n: int) -> tuple[float, float]:
        no_n = n_total - yes_n
        if yes_n == 0 or no_n == 0:
            return 0.0, 0.0
        p = yes_n / n_total
        entropy = -(p * math.log2(p) + (1 - p) * math.log2(1 - p))
        balance = 1.0 - abs(yes_n - no_n) / n_total
        return entropy, balance

    def generate_question(
        self,
        candidates: list[Candidate],
        function_name: str,
        description: str,
        seed_inputs: list[dict[str, Any]] | None = None,
        params: str = "",
    ) -> ClarificationQuestion | None:
        if len(candidates) <= 1 or len(self._questions_asked) >= self.max_questions:
            return None
        probes = self.build_probe_inputs(seed_inputs, params)
        best: ClarificationQuestion | None = None
        for test_input in probes:
            groups = self._partition(candidates, function_name, test_input)
            if len(groups) <= 1:
                continue
            # Turn a possibly multi-way behavioral split into the best binary
            # property: "should output equal Y?". This supports >2 outputs.
            for group in groups:
                # Never ask the user to endorse an execution error as intended behavior.
                # Erroring candidates can still appear in the No partition.
                if isinstance(group["value"], dict) and "__error__" in group["value"]:
                    continue
                yes_ids = list(group["ids"])
                no_ids = [c.index for c in candidates if c.index not in yes_ids]
                info_gain, balance = self._binary_score(len(candidates), len(yes_ids))
                if not no_ids:
                    continue
                q = ClarificationQuestion(
                    question=f"For input {test_input}, should the function return {group['value']!r}?",
                    test_input=test_input,
                    yes_candidate_ids=yes_ids,
                    no_candidate_ids=no_ids,
                    yes_output=group["value"],
                    no_outputs=[g["value"] for g in groups if g is not group],
                    info_gain=info_gain,
                    balance=balance,
                )
                if best is None or (q.info_gain, q.balance) > (best.info_gain, best.balance):
                    best = q
                ideal_balance = 1.0 - abs((len(candidates) // 2) - (len(candidates) - len(candidates) // 2)) / len(candidates)
                if q.balance >= ideal_balance - 1e-12:
                    self._questions_asked.append(q)
                    return q
        if best is not None:
            self._questions_asked.append(best)
        return best

    @property
    def questions_asked(self) -> list[ClarificationQuestion]:
        return list(self._questions_asked)

    @property
    def questions_remaining(self) -> int:
        return max(0, self.max_questions - len(self._questions_asked))

    def reset(self) -> None:
        self._questions_asked = []
