"""Baseline runners sharing the same LLMClient and CodeExecutor as SEMSYNTH."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from src.code_executor import CodeExecutor
from src.llm_client import LLMClient, MockLLMClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = PROJECT_ROOT / "config" / "dataset_sample.json"
RESULTS_DIR = PROJECT_ROOT / "results"


class BaselineRunner:
    def __init__(self, llm_client, dataset_path: Path | str = DATASET_PATH, top_k: int = 1):
        self.llm = llm_client
        self.dataset = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
        self.top_k = top_k
        self.executor = CodeExecutor(timeout=5)

    @staticmethod
    def _infer_params(problem: dict) -> str:
        cases = problem.get("test_cases", [])
        return ", ".join(cases[0]["input"].keys()) if cases else ""

    def run_single(self, problem: dict) -> dict:
        params = self._infer_params(problem)
        started = time.time()
        if self.top_k == 1:
            codes = [self.llm.generate_code(problem["description"], problem["function_name"], params)]
        else:
            codes = self.llm.generate_multiple(problem["description"], problem["function_name"], params, k=self.top_k)
        evaluated = []
        for idx, code in enumerate(codes):
            test_result = self.executor.run_all_tests(code, problem["function_name"], problem["test_cases"])
            evaluated.append({"candidate": idx, "code": code, **test_result})
        # This is an oracle Best-of-K upper bound when top_k>1. It is intentionally
        # labelled as such; it must not be confused with deployable self-selection.
        best = max(evaluated, key=lambda r: r["pass_count"]) if evaluated else None
        return {
            "id": problem["id"],
            "title": problem["title"],
            "passed_all": bool(best and best["passed_all"]),
            "pass_count": best["pass_count"] if best else 0,
            "total_tests": len(problem["test_cases"]),
            "candidates_generated": len(evaluated),
            "best_candidate": best,
            "elapsed_s": round(time.time() - started, 3),
        }

    def run_all(self, limit: int | None = None) -> dict:
        problems = self.dataset[:limit] if limit else self.dataset
        results = [self.run_single(p) for p in problems]
        passed = sum(r["passed_all"] for r in results)
        summary = {
            "experiment": "Direct-1" if self.top_k == 1 else f"Oracle-Best-of-{self.top_k}",
            "provider": getattr(self.llm, "provider", "unknown"),
            "model": getattr(self.llm, "model", "unknown"),
            "total_problems": len(results),
            "passed_problems": passed,
            "task_success_rate": passed / len(results) if results else 0.0,
        }
        return {"summary": summary, "results": results}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Use offline mock client; no API key required")
    parser.add_argument("--top-k", type=int, default=1, help="1 = direct baseline; >1 = oracle Best-of-K upper bound")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    llm = MockLLMClient() if args.dry_run else LLMClient()
    runner = BaselineRunner(llm, top_k=args.top_k)
    result = runner.run_all(args.limit)
    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))
    output = args.output or RESULTS_DIR / ("baseline_direct.json" if args.top_k == 1 else f"baseline_best_of_{args.top_k}.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved: {output}")


if __name__ == "__main__":
    main()
