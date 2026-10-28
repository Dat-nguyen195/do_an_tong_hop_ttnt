from __future__ import annotations

import json
import math
import sys
import types as pytypes
from pathlib import Path

import pytest

from src.baseline_cot import BaselineRunner
from src.candidate_manager import CandidateManager
from src.code_executor import CodeExecutor
from src.llm_client import LLMClient, MockLLMClient, PROVIDER_CONFIG, SUPPORTED_PROVIDERS
from src.question_generator import QuestionGenerator
from src.semsynth_controller import SEMSYNTHConfig, SEMSYNTHController


class DuplicateLLM(LLMClient):
    def __init__(self):
        super().__init__(api_key="dummy")
        self.calls = 0

    def chat(self, user_message, system_message="", **kwargs):
        self.calls += 1
        return "```python\ndef f(x):\n    return x\n```"


class RawDuplicateClient:
    provider = "test"
    model = "duplicate-client"

    def generate_multiple(self, *_args, **_kwargs):
        return [
            "def f(x): return x",
            "def f(x): return x",
            "def f(x): return x + 1",
        ]


class EmptyClient:
    provider = "test"
    model = "empty-client"

    def generate_multiple(self, *_args, **_kwargs):
        return []


def test_gemini_is_supported_provider():
    assert "gemini" in SUPPORTED_PROVIDERS
    assert PROVIDER_CONFIG["gemini"]["env_key"] == "GEMINI_API_KEY"


def test_gemini_uses_provider_default_without_model_overrides(monkeypatch):
    # A local .env may intentionally select a different model. This test checks
    # the fallback configuration, independently of the developer's account.
    monkeypatch.delenv("DEFAULT_MODEL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    client = LLMClient(provider="gemini", api_key="dummy")
    assert client.model == PROVIDER_CONFIG["gemini"]["default_model"]


def test_gemini_missing_key_fails_only_when_client_is_needed(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client = LLMClient(provider="gemini", api_key="")
    assert not client.is_configured
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        client._get_client()


def test_gemini_chat_uses_generate_content(monkeypatch):
    calls = {}

    class FakeConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.update(kwargs)
            return pytypes.SimpleNamespace(text="gemini-ok")

    fake_genai = pytypes.ModuleType("google.genai")
    fake_genai.types = pytypes.SimpleNamespace(GenerateContentConfig=FakeConfig)
    fake_google = pytypes.ModuleType("google")
    fake_google.genai = fake_genai
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    client = LLMClient(provider="gemini", api_key="dummy", model="gemini-test")
    client._client = pytypes.SimpleNamespace(models=FakeModels())
    out = client.chat("hello", system_message="system", temperature=0.4, max_tokens=77)
    assert out == "gemini-ok"
    assert calls["model"] == "gemini-test"
    assert calls["contents"] == "hello"
    assert calls["config"].kwargs["system_instruction"] == "system"
    assert calls["config"].kwargs["max_output_tokens"] == 77


def test_generate_multiple_zero_returns_empty():
    assert MockLLMClient().generate_multiple("anything", "f", "x", k=0) == []


def test_generate_multiple_deduplicates_repeated_model_output():
    llm = DuplicateLLM()
    codes = llm.generate_multiple("identity", "f", "x", k=4)
    assert len(codes) == 1
    assert llm.calls == 12  # bounded at 3*k attempts


def test_extract_code_accepts_capital_python_fence():
    response = "```Python\ndef f():\n    return 1\n```"
    assert LLMClient._extract_code(response).startswith("def f")


def test_executor_allows_math_import():
    ex = CodeExecutor(timeout=1)
    ok, value, error = ex.execute_function("import math\ndef f(x): return math.sqrt(x)", "f", {"x": 9})
    assert ok and value == 3.0 and error == ""


@pytest.mark.parametrize("code", [
    "def f(): return open('x.txt', 'w')",
    "def f(): return eval('1+1')",
    "def f(): return globals()",
    "def f(): return __builtins__['__import__']('os')",
    "def f(x): return x.__class__",
])
def test_executor_rejects_common_escape_paths(code):
    ex = CodeExecutor(timeout=1)
    ok, _, error = ex.execute_function(code, "f", {} if "x" not in code.split("def f(", 1)[1].split(")", 1)[0] else {"x": 1})
    assert not ok
    assert "not allowed" in error


def test_executor_reports_non_json_serializable_input_cleanly():
    ex = CodeExecutor(timeout=1)
    ok, _, error = ex.execute_function("def f(x): return 1", "f", {"x": {1, 2}})
    assert not ok
    assert "not JSON serializable" in error


def test_empty_test_suite_is_not_counted_as_passed_all():
    ex = CodeExecutor()
    result = ex.run_all_tests("def f(): return 1", "f", [])
    assert result["passed_all"] is False
    assert result["pass_count"] == 0


def test_candidate_manager_filter_by_direct_test():
    manager = CandidateManager(CodeExecutor())
    manager.add_candidates(["def f(x): return x", "def f(x): return x + 1"])
    removed = manager.filter_by_test("f", {"x": 3}, 3)
    assert removed == 1
    assert [c.index for c in manager.get_active()] == [0]


def test_probe_inference_recognizes_tuple_style_names_as_sequences():
    qg = QuestionGenerator(max_probe_inputs=1)
    probes = qg.build_probe_inputs(None, "test_tup1, test_tup2")
    assert probes
    assert isinstance(probes[0]["test_tup1"], list)
    assert isinstance(probes[0]["test_tup2"], list)


def test_probe_inference_recognizes_pattern_and_text_as_strings():
    qg = QuestionGenerator(max_probe_inputs=1)
    probe = qg.build_probe_inputs(None, "pattern, text")[0]
    assert isinstance(probe["pattern"], str)
    assert isinstance(probe["text"], str)


def test_list_mutations_include_empty_reverse_and_duplicate():
    vals = QuestionGenerator._mutations([2, 1])
    assert [] in vals
    assert [1, 2] in vals
    assert [2, 1, 2] in vals


def test_binary_score_balanced_split_is_maximal():
    entropy, balance = QuestionGenerator._binary_score(4, 2)
    assert entropy == pytest.approx(1.0)
    assert balance == pytest.approx(1.0)


def test_binary_score_degenerate_split_is_zero():
    assert QuestionGenerator._binary_score(4, 0) == (0.0, 0.0)
    assert QuestionGenerator._binary_score(4, 4) == (0.0, 0.0)


def test_question_generator_does_not_ask_user_to_endorse_error():
    ex = CodeExecutor()
    manager = CandidateManager(ex)
    manager.add_candidates([
        "def f(x): return 1",
        "def f(x): return 1 / 0",
    ])
    q = QuestionGenerator(ex, max_probe_inputs=1).generate_question(
        manager.get_active(), "f", "Return one", seed_inputs=[{"x": 1}], params="x"
    )
    assert q is not None
    assert not (isinstance(q.yes_output, dict) and "__error__" in q.yes_output)
    assert q.yes_output == 1


def test_question_generator_honors_max_questions():
    ex = CodeExecutor()
    manager = CandidateManager(ex)
    manager.add_candidates(["def f(x): return x", "def f(x): return -x"])
    qg = QuestionGenerator(ex, max_questions=1, max_probe_inputs=3)
    first = qg.generate_question(manager.get_active(), "f", "ambiguous", seed_inputs=[{"x": 1}], params="x")
    second = qg.generate_question(manager.get_active(), "f", "ambiguous", seed_inputs=[{"x": 2}], params="x")
    assert first is not None
    assert second is None


def test_controller_deduplicates_custom_client_candidates():
    ctl = SEMSYNTHController(RawDuplicateClient(), SEMSYNTHConfig(top_k=3, max_questions=1, max_probe_inputs=1))
    result = ctl.run("identity maybe plus one", "f", "x", answer_callback=lambda *_: True, seed_inputs=[{"x": 1}])
    assert result.total_candidates == 2


def test_controller_reports_no_result_when_client_returns_no_candidates():
    ctl = SEMSYNTHController(EmptyClient(), SEMSYNTHConfig(top_k=3, max_questions=1, max_probe_inputs=1))
    result = ctl.run("nothing", "f", "x", answer_callback=lambda *_: True, seed_inputs=[{"x": 1}])
    assert result.success is False
    assert result.best_code is None
    assert result.total_candidates == 0


def test_controller_can_be_reused_across_runs():
    ctl = SEMSYNTHController(MockLLMClient(), SEMSYNTHConfig(top_k=3, max_questions=1, max_probe_inputs=1))

    def oracle(_text, q):
        return q.yes_output == list(dict.fromkeys(q.test_input["xs"]))

    r1 = ctl.run("Remove duplicate elements from a list.", "dedup", "xs", oracle, [{"xs": [2, 1, 2]}])
    r2 = ctl.run("Remove duplicate elements from a list.", "dedup", "xs", oracle, [{"xs": [3, 2, 3]}])
    assert r1.total_candidates == r2.total_candidates == 3
    assert len(r1.questions_asked) <= 1 and len(r2.questions_asked) <= 1


def test_dataset_problem_ids_are_unique():
    root = Path(__file__).resolve().parent.parent
    data = json.loads((root / "config" / "dataset_sample.json").read_text(encoding="utf-8"))
    ids = [p["id"] for p in data]
    assert len(ids) == len(set(ids))


def test_dataset_test_cases_have_input_and_expected_output():
    root = Path(__file__).resolve().parent.parent
    data = json.loads((root / "config" / "dataset_sample.json").read_text(encoding="utf-8"))
    for problem in data:
        for tc in problem["test_cases"]:
            assert isinstance(tc["input"], dict)
            assert "expected_output" in tc


def test_baseline_param_inference_uses_test_input_order():
    p = {"test_cases": [{"input": {"alpha": 1, "beta": 2}, "expected_output": 3}]}
    assert BaselineRunner._infer_params(p) == "alpha, beta"


def test_controller_reports_behavioral_indistinguishability_reason():
    ctl = SEMSYNTHController(MockLLMClient(), SEMSYNTHConfig(top_k=3, max_questions=3, max_probe_inputs=4))

    def oracle(_text, q):
        return q.yes_output == list(dict.fromkeys(q.test_input["xs"]))

    result = ctl.run(
        "Remove duplicate elements from a list.",
        "dedup",
        "xs",
        oracle,
        [{"xs": [3, 1, 3, 2]}],
    )
    assert result.remaining_candidates == 2
    assert result.metadata["termination_reason"] == "no_distinguishing_question"
