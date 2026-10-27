from __future__ import annotations

import json
from pathlib import Path

from src.candidate_manager import CandidateManager
from src.code_executor import CodeExecutor
from src.llm_client import LLMClient, MockLLMClient
from src.question_generator import QuestionGenerator
from src.semsynth_controller import SEMSYNTHConfig, SEMSYNTHController


class RecordingLLM(LLMClient):
    def __init__(self):
        super().__init__(api_key="dummy")
        self.temperatures = []
        self.counter = 0

    def chat(self, user_message, system_message="", **kwargs):
        self.temperatures.append(kwargs.get("temperature"))
        self.counter += 1
        return f"```python\ndef f(xs):\n    return {self.counter}\n```"


def test_generate_multiple_uses_sampling_temperature():
    llm = RecordingLLM()
    codes = llm.generate_multiple("Return something", "f", "xs", k=3)
    assert len(codes) == 3
    assert len(set(llm.temperatures)) >= 2
    assert all(t is not None and t > 0 for t in llm.temperatures[:3])


def test_executor_rejects_os_import():
    ex = CodeExecutor(timeout=1)
    ok, _, error = ex.execute_function("import os\ndef f(): return 1", "f", {})
    assert not ok
    assert "not allowed" in error


def test_candidate_manager_partition_filter():
    manager = CandidateManager(CodeExecutor())
    manager.add_candidates(["def f(x): return 1", "def f(x): return 2", "def f(x): return 1"])
    removed = manager.filter_by_answer(
        "Should it return 1?", True,
        yes_candidate_ids=[0, 2], no_candidate_ids=[1],
    )
    assert removed == 1
    assert [c.index for c in manager.get_active()] == [0, 2]


def test_question_generator_finds_balanced_behavior_split():
    ex = CodeExecutor()
    manager = CandidateManager(ex)
    manager.add_candidates([
        "def f(xs): return list(dict.fromkeys(xs))",
        "def f(xs): return sorted(set(xs))",
    ])
    q = QuestionGenerator(ex).generate_question(
        manager.get_active(), "f", "Remove duplicates", seed_inputs=[{"xs": [3, 1, 3]}], params="xs"
    )
    assert q is not None
    assert q.balance == 1.0
    assert sorted(q.yes_candidate_ids + q.no_candidate_ids) == [0, 1]


def test_controller_end_to_end_offline():
    controller = SEMSYNTHController(MockLLMClient(), SEMSYNTHConfig(top_k=3, max_questions=3))

    def oracle(_text, q):
        expected = list(dict.fromkeys(q.test_input["xs"]))
        return q.yes_output == expected

    result = controller.run(
        "Remove duplicate elements from a list.",
        "remove_duplicates",
        "xs",
        answer_callback=oracle,
        seed_inputs=[{"xs": [3, 1, 3, 2]}],
    )
    assert result.success
    assert result.questions_asked
    assert "dict.fromkeys" in result.best_code or "if x not in out" in result.best_code
    assert result.remaining_candidates < result.total_candidates


def test_he008_domain_fixed():
    root = Path(__file__).resolve().parent.parent
    data = json.loads((root / "config" / "dataset_sample.json").read_text(encoding="utf-8"))
    he008 = next(x for x in data if x["id"] == "HE_008")
    assert he008["domain"] == "list"
