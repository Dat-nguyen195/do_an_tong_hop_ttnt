"""Kaggle-friendly SEMSYNTH runner.

Examples:
    python kaggle_run.py --offline
    python kaggle_run.py --offline-suite
    python kaggle_run.py --provider gemini --model gemini-3.8-flash
"""
from __future__ import annotations

import argparse
import json

from src.llm_client import LLMClient, MockLLMClient
from src.semsynth_controller import SEMSYNTHConfig, SEMSYNTHController


def _run_case(description, function_name, params, seed_inputs, oracle, *, top_k=5, max_questions=4, llm=None):
    controller = SEMSYNTHController(
        llm or MockLLMClient(),
        SEMSYNTHConfig(top_k=top_k, max_questions=max_questions),
    )
    result = controller.run(
        description=description,
        function_name=function_name,
        params=params,
        answer_callback=oracle,
        seed_inputs=seed_inputs,
    )
    return result


def run_offline_suite(top_k: int, max_questions: int) -> None:
    cases = []

    def dedup_oracle(_text, q):
        xs = q.test_input["xs"]
        expected = list(dict.fromkeys(xs))
        return q.yes_output == expected

    cases.append((
        "remove_duplicates",
        _run_case(
            "Remove duplicate elements from a list.",
            "remove_duplicates", "xs", [{"xs": [3, 1, 3, 2]}], dedup_oracle,
            top_k=top_k, max_questions=max_questions,
        ),
    ))

    def sort_oracle(_text, q):
        expected = sorted(q.test_input["xs"])
        return q.yes_output == expected

    cases.append((
        "sort_numbers",
        _run_case(
            "Sort the numbers in a list.",
            "sort_numbers", "xs", [{"xs": [3, 1, 2]}], sort_oracle,
            top_k=top_k, max_questions=max_questions,
        ),
    ))

    def common_oracle(_text, q):
        expected = sorted(set(q.test_input["a"]) & set(q.test_input["b"]))
        return q.yes_output == expected

    cases.append((
        "common_elements",
        _run_case(
            "Return the common elements of two lists.",
            "common_elements", "a, b", [{"a": [3, 1, 3, 2], "b": [3, 2, 4]}], common_oracle,
            top_k=top_k, max_questions=max_questions,
        ),
    ))

    print("\n=== OFFLINE SEMSYNTH SUITE ===")
    for name, result in cases:
        print(json.dumps({
            "case": name,
            "success": result.success,
            "total_candidates": result.total_candidates,
            "remaining_candidates": result.remaining_candidates,
            "questions": len(result.questions_asked),
            "converged": result.metadata.get("converged"),
            "termination_reason": result.metadata.get("termination_reason"),
        }, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--offline-suite", action="store_true", help="Run 3 deterministic ambiguity smoke cases")
    parser.add_argument("--provider", default="gemini", choices=["gemini", "openai", "openrouter"])
    parser.add_argument("--model", default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-questions", type=int, default=4)
    args = parser.parse_args()

    if args.offline_suite:
        run_offline_suite(args.top_k, args.max_questions)
        return

    llm = MockLLMClient() if args.offline else LLMClient(provider=args.provider, model=args.model)
    controller = SEMSYNTHController(
        llm,
        SEMSYNTHConfig(top_k=args.top_k, max_questions=args.max_questions),
    )

    description = "Remove duplicate elements from a list."
    seed_inputs = [{"xs": [3, 1, 3, 2]}]

    # The CLI must stay non-interactive in Kaggle. For this smoke case, the
    # simulated intent is "remove duplicates while preserving first occurrence".
    def simulated_user(_text, q):
        expected = list(dict.fromkeys(q.test_input["xs"]))
        return q.yes_output == expected

    result = controller.run(
        description=description,
        function_name="remove_duplicates",
        params="xs",
        answer_callback=simulated_user,
        seed_inputs=seed_inputs,
    )
    print("\n=== SEMSYNTH KAGGLE SMOKE DEMO ===")
    print(json.dumps({
        "provider": result.metadata.get("provider"),
        "model": result.metadata.get("model"),
        "success": result.success,
        "total_candidates": result.total_candidates,
        "remaining_candidates": result.remaining_candidates,
        "questions": result.questions_asked,
    }, indent=2, ensure_ascii=False))
    print("\nBest code:\n")
    print(result.best_code)


if __name__ == "__main__":
    main()
