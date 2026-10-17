"""Behavioral disagreement search and balanced Yes/No question selection."""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
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
    def __init__(self, executor: CodeExecutor | None = None, max_questions: int = 5, max_probe_inputs: int = 12,
                 strategy: str = "balanced", random_seed: int = 0):
        if strategy not in {"balanced", "random"}:
            raise ValueError("strategy must be balanced or random")
        self.strategy = strategy
        self.rng = random.Random(random_seed)
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
                if any(t in n for t in ("list", "nums", "numbers", "array", "arr", "items", "values")) or n in {"xs", "ys", "test_tup1", "test_tup2", "tup1", "tup2"} or "tuple" in n or "tup" in n:
                    default[name] = [2, 1, 2]
                elif any(t in n for t in ("string", "str", "text", "word", "pattern", "prefix", "suffix")) or n in {"s", "ch", "char", "sub_str"}:
                    default[name] = "aba"
                elif n in {"n", "k", "x", "y", "threshold", "limit", "count", "size"}:
                    default[name] = 2
                else:
                    default[name] = 1
            if default:
                seeds = [default]
        probes: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(item: dict[str, Any]) -> None:
            key = _freeze(item)
            if key not in seen and len(probes) < self.max_probe_inputs:
                seen.add(key)
                probes.append(item)

        # Cover the original seeds, then single-coordinate mutations in
        # round-robin order. This avoids starving later parameters when a
        # truncated Cartesian product only varies the first parameter.
        for seed in seeds:
            add(dict(seed))
        for seed in seeds:
            mutated = {key: self._mutations(value) for key, value in seed.items()}
            depth = max((len(v) for v in mutated.values()), default=0)
            for i in range(1, depth):
                for key, choices in mutated.items():
                    if i < len(choices):
                        item = dict(seed)
                        item[key] = choices[i]
                        add(item)
                        if len(probes) == self.max_probe_inputs:
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
    def _entropy(p: float) -> float:
        return -(p * math.log2(p) + (1 - p) * math.log2(1 - p)) if 0 < p < 1 else 0.0

    @classmethod
    def _weighted_score(cls, candidates: list[Candidate], yes_ids: list[int], error_rate: float) -> float:
        weights = [max(0.0, c.score) for c in candidates]
        total = sum(weights)
        if total <= 0:
            return 0.0
        yes = sum(max(0.0, c.score) for c in candidates if c.index in yes_ids) / total
        observed_yes = error_rate + (1.0 - 2.0 * error_rate) * yes
        return cls._entropy(observed_yes) - cls._entropy(error_rate)

    @staticmethod
    def _semantic_question(description: str, test_input: dict[str, Any], yes_output: Any) -> str | None:
        """Use a short semantic property only if output equality grounds it.

        No LLM-generated semantic label is trusted to define the split.
        """
        d = description.lower()
        if "duplicate" in d:
            for value in test_input.values():
                if isinstance(value, list):
                    try:
                        stable = list(dict.fromkeys(value))
                        if stable != sorted(set(value)) and yes_output == stable:
                            return "Should duplicate removal preserve the order of first occurrences?"
                    except TypeError:
                        pass
        if "sort" in d:
            for value in test_input.values():
                if isinstance(value, list):
                    try:
                        if sorted(value) != sorted(value, reverse=True):
                            if yes_output == sorted(value):
                                return "Should the numbers be sorted in ascending order?"
                            if yes_output == sorted(value, reverse=True):
                                return "Should the numbers be sorted in descending order?"
                    except TypeError:
                        pass
        return None

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
        error_rate: float | None = None,
        semantic: bool = False,
    ) -> ClarificationQuestion | None:
        if len(candidates) <= 1 or len(self._questions_asked) >= self.max_questions:
            return None
        probes = self.build_probe_inputs(seed_inputs, params)
        # Pre-fill the same single-probe cache in bounded batches. Separate
        # candidate namespaces are used for every probe within the subprocess.
        if hasattr(self.executor, "execute_batch") and getattr(self.executor, "cache_size", 0):
            for candidate in candidates:
                self.executor.execute_batch(candidate.code, function_name, probes)
        best: ClarificationQuestion | None = None
        alternatives: list[ClarificationQuestion] = []
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
                if error_rate is not None:
                    info_gain = self._weighted_score(candidates, yes_ids, error_rate)
                if not no_ids:
                    continue
                phrasing = self._semantic_question(description, test_input, group["value"]) if semantic else None
                prompt = phrasing or f"For input {test_input}, should the function return {group['value']!r}?"
                # Do not repeat an identical question, even across probe rounds.
                if any(old.question == prompt for old in self._questions_asked):
                    continue
                q = ClarificationQuestion(
                    question=prompt,
                    test_input=test_input,
                    yes_candidate_ids=yes_ids,
                    no_candidate_ids=no_ids,
                    yes_output=group["value"],
                    no_outputs=[g["value"] for g in groups if g is not group],
                    info_gain=info_gain,
                    balance=balance,
                )
                alternatives.append(q)
                if best is None or (q.info_gain, q.balance) > (best.info_gain, best.balance):
                    best = q
                ideal_balance = 1.0 - abs((len(candidates) // 2) - (len(candidates) - len(candidates) // 2)) / len(candidates)
                if self.strategy == "balanced" and error_rate is None and q.balance >= ideal_balance - 1e-12:
                    self._questions_asked.append(q)
                    return q
        if self.strategy == "random" and alternatives:
            best = self.rng.choice(alternatives)
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
