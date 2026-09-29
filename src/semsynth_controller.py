"""End-to-end SEMSYNTH controller."""
from __future__ import annotations
from dataclasses import dataclass, field
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
        self.executor = CodeExecutor(timeout=self.config.execution_timeout)
        self.candidate_manager = CandidateManager(self.executor)
        self.question_generator = QuestionGenerator(
            self.executor,
            max_questions=self.config.max_questions,
            max_probe_inputs=self.config.max_probe_inputs,
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
        self.candidate_manager.add_candidates(unique_codes)
        transcript: list[dict[str, Any]] = []

        while not self.candidate_manager.is_converged:
            active = self.candidate_manager.get_active()
            question = self.question_generator.generate_question(
                active, function_name, description, seed_inputs=seed_inputs, params=params
            )
            if question is None:
                break
            try:
                answer = bool(answer_callback(question.question, question))
            except TypeError:
                answer = bool(answer_callback(question.question))
            before = self.candidate_manager.active_count
            removed = self.candidate_manager.filter_by_answer(
                question.question,
                answer,
                yes_candidate_ids=question.yes_candidate_ids,
                no_candidate_ids=question.no_candidate_ids,
            )
            transcript.append({
                "question": question.question,
                "answer": answer,
                "test_input": question.test_input,
                "yes_candidate_ids": question.yes_candidate_ids,
                "no_candidate_ids": question.no_candidate_ids,
                "info_gain": round(question.info_gain, 6),
                "balance": round(question.balance, 6),
                "candidates_before": before,
                "removed": removed,
                "candidates_after": self.candidate_manager.active_count,
            })
            if removed == 0:
                break

        best = self.candidate_manager.get_best()
        return SessionResult(
            success=best is not None,
            best_code=best.code if best else None,
            questions_asked=transcript,
            total_candidates=self.candidate_manager.total_count,
            remaining_candidates=self.candidate_manager.active_count,
            metadata={
                "provider": getattr(self.llm, "provider", "unknown"),
                "model": getattr(self.llm, "model", "unknown"),
                "converged": self.candidate_manager.is_converged,
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
