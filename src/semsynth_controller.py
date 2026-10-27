"""End-to-end SEMSYNTH controller."""
from __future__ import annotations
from dataclasses import dataclass, field
import ast
from typing import Any, Callable

from src.candidate_manager import CandidateManager
from src.code_executor import CodeExecutor
from src.question_generator import QuestionGenerator


@dataclass
class SEMSYNTHConfig:
    top_k: int = 5
    max_questions: int = 4
    execution_timeout: int = 5
    max_probe_inputs: int = 12
    belief_mode: str = "hard"  # hard (original) or soft (noise-aware Bayesian)
    answer_error_rate: float = 0.10
    posterior_threshold: float = 0.95
    semantic_questions: bool = False
    explain_questions: bool = False  # Trace only; never changes decision rules
    enable_execution_cache: bool = True
    selection_strategy: str = "balanced"
    selection_seed: int = 0


@dataclass
class SessionResult:
    success: bool
    best_code: str | None
    questions_asked: list[dict[str, Any]] = field(default_factory=list)
    total_candidates: int = 0
    remaining_candidates: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class SEMSYNTHController:
    def __init__(self, llm_client, config: SEMSYNTHConfig | None = None):
        self.llm = llm_client
        self.config = config or SEMSYNTHConfig()
        if self.config.belief_mode not in {"hard", "soft"}:
            raise ValueError("belief_mode must be hard or soft")
        if not (0 < self.config.answer_error_rate < 0.5):
            raise ValueError("answer_error_rate must be between 0 and 0.5")
        if not (0.5 < self.config.posterior_threshold <= 1):
            raise ValueError("posterior_threshold must be in (0.5, 1]")
        self.executor = CodeExecutor(timeout=self.config.execution_timeout,
                                     enable_cache=self.config.enable_execution_cache)
        self.candidate_manager = CandidateManager(self.executor)
        self.question_generator = QuestionGenerator(
            self.executor,
            max_questions=self.config.max_questions,
            max_probe_inputs=self.config.max_probe_inputs,
            strategy=self.config.selection_strategy,
            random_seed=self.config.selection_seed,
        )

    def run(
        self,
        description: str,
        function_name: str,
        params: str = "",
        answer_callback: Callable[..., bool] | None = None,
        seed_inputs: list[dict[str, Any]] | None = None,
    ) -> SessionResult:
        self.reset()
        answer_callback = answer_callback or self._default_answer_callback
        raw_codes = self.llm.generate_multiple(description, function_name, params, k=self.config.top_k)
        # de-duplicate defensively even for custom clients
        unique_codes = list(dict.fromkeys(code.strip() for code in raw_codes if code and code.strip()))
        valid_codes = []
        rejected = []
        for code in unique_codes:
            try:
                self.executor.validate_code(code)
                tree = ast.parse(code)
                if not any(isinstance(node, ast.FunctionDef) and node.name == function_name
                           for node in tree.body):
                    raise ValueError(f"Missing function {function_name}")
                valid_codes.append(code)
            except (SyntaxError, ValueError) as exc:
                rejected.append({"error": f"{type(exc).__name__}: {exc}"})
        self.candidate_manager.add_candidates(valid_codes)
        if self.config.belief_mode == "soft" and self.candidate_manager.active_count:
            for candidate in self.candidate_manager.get_active():
                candidate.score = 1.0 / self.candidate_manager.active_count
        transcript: list[dict[str, Any]] = []
        termination_reason: str | None = None

        if self.candidate_manager.active_count == 0:
            termination_reason = "no_candidates"

        while not self.candidate_manager.is_converged:
            if self.config.belief_mode == "soft":
                current_best = self.candidate_manager.get_best()
                if current_best and current_best.score >= self.config.posterior_threshold:
                    termination_reason = "posterior_confident"
                    break
            active = self.candidate_manager.get_active()
            question = self.question_generator.generate_question(
                active, function_name, description, seed_inputs=seed_inputs, params=params,
                error_rate=self.config.answer_error_rate if self.config.belief_mode == "soft" else None,
                semantic=self.config.semantic_questions,
            )
            if question is None:
                termination_reason = (
                    "question_budget_exhausted"
                    if self.question_generator.questions_remaining == 0
                    else "no_distinguishing_question"
                )
                break
            try:
                answer = bool(answer_callback(question.question, question))
            except TypeError:
                answer = bool(answer_callback(question.question))
            before = self.candidate_manager.active_count
            prior = {str(c.index): round(c.score, 10) for c in active}
            predictive_yes = sum(c.score for c in active if c.index in question.yes_candidate_ids)
            predictive_total = sum(c.score for c in active)
            if predictive_total > 0:
                predictive_yes /= predictive_total
            else:
                predictive_yes = len(question.yes_candidate_ids) / len(active)
            likelihood = (
                self.config.answer_error_rate +
                (1 - 2 * self.config.answer_error_rate) *
                (predictive_yes if answer else 1 - predictive_yes)
                if self.config.belief_mode == "soft" else None
            )
            if self.config.belief_mode == "soft":
                yes_ids = set(question.yes_candidate_ids)
                eps = self.config.answer_error_rate
                normalizer = 0.0
                for candidate in active:
                    agrees = ((candidate.index in yes_ids) == answer)
                    candidate.score *= (1 - eps) if agrees else eps
                    normalizer += candidate.score
                if normalizer > 0:
                    for candidate in active:
                        candidate.score /= normalizer
                removed = 0
            else:
                removed = self.candidate_manager.filter_by_answer(
                    question.question,
                    answer,
                    yes_candidate_ids=question.yes_candidate_ids,
                    no_candidate_ids=question.no_candidate_ids,
                )
            event = {
                "question": question.question,
                "question_type": question.question_type,
                "answer": answer,
                "test_input": question.test_input,
                "yes_candidate_ids": question.yes_candidate_ids,
                "no_candidate_ids": question.no_candidate_ids,
                "info_gain": round(question.info_gain, 6),
                "balance": round(question.balance, 6),
                "candidates_before": before,
                "removed": removed,
                "candidates_after": self.candidate_manager.active_count,
                "posterior_max": round(self.candidate_manager.get_best().score, 8)
                if self.config.belief_mode == "soft" else None,
            }
            if self.config.explain_questions:
                event["explanation"] = question.explanation
                event["belief_before"] = prior
                event["belief_after"] = {
                    str(c.index): round(c.score, 10)
                    for c in self.candidate_manager.get_active()
                }
                event["answer_predictive_likelihood"] = (
                    round(likelihood, 8) if likelihood is not None else None
                )
                # An improbable answer signals a need to check evidence; it is
                # NOT automatically a contradiction and must not be discarded.
                event["needs_answer_review"] = bool(
                    likelihood is not None and likelihood < 0.20
                )
            transcript.append(event)
            if removed == 0 and self.config.belief_mode == "hard":
                termination_reason = "non_discriminating_answer"
                break

        if termination_reason is None:
            termination_reason = (
                "single_candidate"
                if self.candidate_manager.active_count == 1
                else "no_candidates"
                if self.candidate_manager.active_count == 0
                else "stopped"
            )

        best = self.candidate_manager.get_best()
        confident = bool(best and (self.candidate_manager.active_count == 1
                         if self.config.belief_mode == "hard"
                         else best.score >= self.config.posterior_threshold))
        if self.config.belief_mode == "soft" and termination_reason == "single_candidate":
            confident = True
        return SessionResult(
            success=best is not None,
            best_code=best.code if best else None,
            questions_asked=transcript,
            total_candidates=self.candidate_manager.total_count,
            remaining_candidates=self.candidate_manager.active_count,
            metadata={
                "provider": getattr(self.llm, "provider", "unknown"),
                "model": getattr(self.llm, "model", "unknown"),
                "converged": confident,
                "has_candidate": best is not None,
                "selection_status": "confident" if confident else "tentative" if best else "empty",
                "success_definition": "candidate_exists; NOT held-out test correctness",
                "termination_reason": termination_reason,
                "belief_mode": self.config.belief_mode,
                "semantic_questions": self.config.semantic_questions,
                "explain_questions": self.config.explain_questions,
                "posterior": {str(c.index): round(c.score, 8) for c in self.candidate_manager.get_active()}
                if self.config.belief_mode == "soft" else None,
                "rejected_candidates": rejected,
                "executor_stats": self.executor.stats,
                "candidate_history": self.candidate_manager.history,
            },
        )

    @staticmethod
    def _default_answer_callback(question: str, *_args) -> bool:
        while True:
            answer = input(f"\n{question}\n(Y)es / (N)o: ").strip().lower()
            if answer in {"y", "yes", "true", "1"}:
                return True
            if answer in {"n", "no", "false", "0"}:
                return False

    def reset(self) -> None:
        self.candidate_manager = CandidateManager(self.executor)
        self.question_generator.reset()
