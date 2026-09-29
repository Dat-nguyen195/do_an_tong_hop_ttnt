"""Kaggle-friendly smoke demo.

Usage after cloning the repo in a Kaggle notebook:
    !pip install -q -r requirements.txt
    !python kaggle_run.py --offline

Real LLM mode:
    set OPENAI_API_KEY or OPENROUTER_API_KEY from Kaggle Secrets, then
    !python kaggle_run.py --provider openai --model gpt-4o-mini
"""
from __future__ import annotations

import argparse
import json

from src.llm_client import LLMClient, MockLLMClient
from src.semsynth_controller import SEMSYNTHConfig, SEMSYNTHController


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--provider", default="openai", choices=["openai", "openrouter"])
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    llm = MockLLMClient() if args.offline else LLMClient(provider=args.provider, model=args.model)
    controller = SEMSYNTHController(llm, SEMSYNTHConfig(top_k=5, max_questions=4))

    # A deliberately underspecified task.  The simulated user intent is to keep
    # first-occurrence order.  This makes the offline smoke test reproducible.
    description = "Remove duplicate elements from a list."
    seed_inputs = [{"xs": [3, 1, 3, 2]}]

    def simulated_user(_text, q):
        # Reference intent for the smoke demo only, not a research evaluation.
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
        "success": result.success,
        "total_candidates": result.total_candidates,
        "remaining_candidates": result.remaining_candidates,
        "questions": result.questions_asked,
    }, indent=2, ensure_ascii=False))
    print("\nBest code:\n")
    print(result.best_code)


if __name__ == "__main__":
    main()
