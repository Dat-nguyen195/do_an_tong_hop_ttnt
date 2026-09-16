"""
SEMSYNTH Lite — Baseline CoT (Chain-of-Thought)
================================================
Baseline thí nghiệm: Gọi LLM sinh mã 1-shot trực tiếp từ mô tả bài toán,
sử dụng kỹ thuật Chain-of-Thought prompting. Không có tương tác (0-interaction).

Mục đích: Làm đối chứng (baseline) cho phương pháp SEMSYNTH Lite có đặt câu hỏi.

Cách sử dụng:
    1. Tạo file .env với OPENAI_API_KEY=sk-...
    2. Chạy: python src/baseline_cot.py
    3. Xem kết quả trong console và file results/baseline_results.json

Hỗ trợ backend:
    - OpenAI API (mặc định)
    - OpenRouter (đặt OPENROUTER_API_KEY và LLM_PROVIDER=openrouter)
"""

import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Đường dẫn mặc định
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = PROJECT_ROOT / "config" / "dataset_sample.json"
RESULTS_DIR = PROJECT_ROOT / "results"

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # "openai" hoặc "openrouter"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Model mặc định
DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "openrouter": "meta-llama/llama-3-70b-instruct",
}

MODEL_NAME = os.getenv("LLM_MODEL", DEFAULT_MODELS.get(LLM_PROVIDER, "gpt-4o-mini"))


# ---------------------------------------------------------------------------
# Prompt Template — Chain-of-Thought
# ---------------------------------------------------------------------------

COT_SYSTEM_PROMPT = """\
You are an expert Python programmer. When given a programming task description, \
you will:

1. **Analyze** the problem carefully, identifying inputs, outputs, edge cases, \
and constraints.
2. **Think step-by-step** about the algorithm and approach.
3. **Write** a complete, correct Python function that solves the problem.

Return ONLY the Python function code inside a ```python``` code block. \
Do not include test cases, examples, or explanations outside the code block.\
"""

COT_USER_PROMPT_TEMPLATE = """\
## Task
{description}

## Function Signature
```python
def {function_name}({params}):
```

## Requirements
- Think step-by-step before writing the code.
- Handle edge cases (empty inputs, single elements, etc.).
- Return the correct output type.
- Write clean, readable Python code.

Please provide the complete function implementation.\
"""


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------

class LLMClient:
    """Wrapper cho OpenAI-compatible API (OpenAI / OpenRouter)."""

    def __init__(self, provider: str = "openai", model: str = "gpt-4o-mini"):
        self.provider = provider
        self.model = model
        self._client = None

    def _get_client(self):
        """Lazy initialization của OpenAI client."""
        if self._client is not None:
            return self._client

        try:
            from openai import OpenAI
        except ImportError:
            print("❌ Cần cài đặt thư viện openai: pip install openai")
            sys.exit(1)

        if self.provider == "openrouter":
            api_key = OPENROUTER_API_KEY
            base_url = "https://openrouter.ai/api/v1"
        else:
            api_key = OPENAI_API_KEY
            base_url = None  # Mặc định OpenAI

        if not api_key:
            print(f"❌ Thiếu API key cho provider '{self.provider}'.")
            print(f"   Hãy đặt biến môi trường: "
                  f"{'OPENROUTER_API_KEY' if self.provider == 'openrouter' else 'OPENAI_API_KEY'}")
            sys.exit(1)

        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url

        self._client = OpenAI(**kwargs)
        return self._client

    def generate_code(self, description: str, function_name: str,
                      params: str = "") -> str:
        """
        Gọi LLM để sinh mã Python từ mô tả bài toán.

        Args:
            description: Mô tả bài toán bằng NL.
            function_name: Tên hàm cần sinh.
            params: Danh sách tham số (dạng chuỗi).

        Returns:
            Mã Python được sinh ra (đã trích xuất từ code block).
        """
        client = self._get_client()

        user_prompt = COT_USER_PROMPT_TEMPLATE.format(
            description=description,
            function_name=function_name,
            params=params,
        )

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": COT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,  # Deterministic cho reproducibility
            max_tokens=1024,
        )

        raw_response = response.choices[0].message.content or ""
        return self._extract_code(raw_response)

    @staticmethod
    def _extract_code(response: str) -> str:
        """Trích xuất mã Python từ response có markdown code block."""
        # Tìm code block ```python ... ```
        if "```python" in response:
            start = response.index("```python") + len("```python")
            end = response.index("```", start)
            return response[start:end].strip()
        elif "```" in response:
            start = response.index("```") + 3
            # Bỏ qua tên ngôn ngữ nếu có trên cùng dòng
            newline_pos = response.index("\n", start)
            start = newline_pos + 1
            end = response.index("```", start)
            return response[start:end].strip()
        else:
            # Không có code block, trả về nguyên văn
            return response.strip()


# ---------------------------------------------------------------------------
# Code Executor — Sandbox đơn giản
# ---------------------------------------------------------------------------

class CodeExecutor:
    """Chạy mã Python ứng viên trong sandbox đơn giản và kiểm tra kết quả."""

    @staticmethod
    def execute_function(code: str, function_name: str,
                         test_input: dict[str, Any]) -> tuple[bool, Any, str]:
        """
        Thực thi hàm đã sinh và trả về kết quả.

        Args:
            code: Mã nguồn Python.
            function_name: Tên hàm cần gọi.
            test_input: Dict các tham số đầu vào.

        Returns:
            Tuple (success: bool, result: Any, error_message: str)
        """
        # Tạo namespace cô lập
        namespace: dict[str, Any] = {}

        try:
            # Thực thi mã để định nghĩa hàm
            exec(code, namespace)  # noqa: S102

            if function_name not in namespace:
                return False, None, f"Function '{function_name}' not found in generated code."

            func = namespace[function_name]

            # Gọi hàm với test input
            import copy
            safe_input = copy.deepcopy(test_input)
            result = func(**safe_input)

            return True, result, ""

        except Exception as e:
            return False, None, f"{type(e).__name__}: {e}"

    @staticmethod
    def run_test_case(code: str, function_name: str,
                      test_case: dict) -> dict:
        """
        Chạy một test case và trả về kết quả chi tiết.

        Returns:
            Dict chứa: passed, input, expected, actual, error
        """
        test_input = test_case["input"]
        expected = test_case["expected_output"]

        success, actual, error = CodeExecutor.execute_function(
            code, function_name, test_input
        )

        passed = success and actual == expected

        return {
            "passed": passed,
            "input": test_input,
            "expected": expected,
            "actual": actual,
            "error": error if not success else None,
        }


# ---------------------------------------------------------------------------
# Baseline Runner
# ---------------------------------------------------------------------------

class BaselineCoTRunner:
    """
    Chạy thí nghiệm Baseline CoT trên tập dataset.

    Quy trình cho mỗi bài toán:
        1. Đọc mô tả NL từ dataset.
        2. Gọi LLM sinh mã 1-shot (CoT prompting).
        3. Chạy mã qua tất cả test cases.
        4. Ghi nhận Pass/Fail.
    """

    def __init__(self, llm_client: LLMClient, dataset_path: Path | str):
        self.llm = llm_client
        self.dataset = self._load_dataset(dataset_path)
        self.results: list[dict] = []

    @staticmethod
    def _load_dataset(path: Path | str) -> list[dict]:
        """Đọc dataset từ file JSON."""
        path = Path(path)
        if not path.exists():
            print(f"❌ Không tìm thấy dataset tại: {path}")
            sys.exit(1)

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        print(f"📂 Đã tải dataset: {len(data)} bài toán từ {path.name}")
        return data

    @staticmethod
    def _infer_params(test_cases: list[dict]) -> str:
        """Suy luận danh sách tham số từ test cases."""
        if not test_cases:
            return ""
        first_input = test_cases[0].get("input", {})
        return ", ".join(first_input.keys())

    def run_single(self, problem: dict) -> dict:
        """
        Chạy Baseline CoT cho một bài toán.

        Returns:
            Dict kết quả chứa: id, title, generated_code, test_results, passed_all, ...
        """
        problem_id = problem["id"]
        title = problem["title"]
        description = problem["description"]
        function_name = problem["function_name"]
        test_cases = problem["test_cases"]
        params = self._infer_params(test_cases)

        print(f"\n{'='*60}")
        print(f"🔍 [{problem_id}] {title}")
        print(f"   Mô tả: {description[:80]}...")
        print(f"   Hàm: {function_name}({params})")

        # Bước 1: Gọi LLM sinh mã
        start_time = time.time()
        try:
            generated_code = self.llm.generate_code(description, function_name, params)
            generation_time = time.time() - start_time
            print(f"   ⏱️  Thời gian sinh mã: {generation_time:.2f}s")
            print(f"   📝 Mã sinh ra:\n{'─'*40}")
            for line in generated_code.split("\n"):
                print(f"      {line}")
            print(f"{'─'*40}")
        except Exception as e:
            generation_time = time.time() - start_time
            error_msg = f"{type(e).__name__}: {e}"
            print(f"   ❌ Lỗi khi sinh mã: {error_msg}")
            return {
                "id": problem_id,
                "title": title,
                "generated_code": None,
                "generation_time_s": generation_time,
                "test_results": [],
                "passed_all": False,
                "pass_count": 0,
                "total_tests": len(test_cases),
                "error": error_msg,
            }

        # Bước 2: Chạy test cases
        executor = CodeExecutor()
        test_results = []
        pass_count = 0

        for i, tc in enumerate(test_cases):
            result = executor.run_test_case(generated_code, function_name, tc)
            test_results.append(result)

            status = "✅" if result["passed"] else "❌"
            print(f"   Test {i+1}: {status}  "
                  f"Input={result['input']}  "
                  f"Expected={result['expected']}  "
                  f"Got={result['actual']}")

            if result["passed"]:
                pass_count += 1

        passed_all = pass_count == len(test_cases)
        status_icon = "🎉" if passed_all else "⚠️"
        print(f"   {status_icon} Kết quả: {pass_count}/{len(test_cases)} tests passed")

        return {
            "id": problem_id,
            "title": title,
            "generated_code": generated_code,
            "generation_time_s": round(generation_time, 3),
            "test_results": test_results,
            "passed_all": passed_all,
            "pass_count": pass_count,
            "total_tests": len(test_cases),
            "error": None,
        }

    def run_all(self) -> dict:
        """
        Chạy Baseline CoT trên toàn bộ dataset.

        Returns:
            Dict tổng kết: summary + chi tiết từng bài.
        """
        print("\n" + "=" * 60)
        print("🚀 SEMSYNTH Lite — Baseline CoT Experiment")
        print(f"   Provider: {self.llm.provider}")
        print(f"   Model: {self.llm.model}")
        print(f"   Dataset: {len(self.dataset)} bài toán")
        print("=" * 60)

        self.results = []
        total_start = time.time()

        for problem in self.dataset:
            result = self.run_single(problem)
            self.results.append(result)

        total_time = time.time() - total_start

        # Tổng kết
        total_problems = len(self.results)
        passed_problems = sum(1 for r in self.results if r["passed_all"])
        success_rate = (passed_problems / total_problems * 100) if total_problems > 0 else 0

        summary = {
            "experiment": "Baseline CoT (0-interaction)",
            "model": self.llm.model,
            "provider": self.llm.provider,
            "total_problems": total_problems,
            "passed_problems": passed_problems,
            "success_rate_percent": round(success_rate, 2),
            "total_time_s": round(total_time, 3),
            "avg_time_per_problem_s": round(total_time / max(total_problems, 1), 3),
        }

        print("\n" + "=" * 60)
        print("📊 TỔNG KẾT THÍ NGHIỆM BASELINE CoT")
        print("=" * 60)
        print(f"   Tổng bài toán:    {total_problems}")
        print(f"   Pass toàn bộ TC:  {passed_problems}/{total_problems}")
        print(f"   Success Rate:     {success_rate:.1f}%")
        print(f"   Tổng thời gian:   {total_time:.1f}s")
        print(f"   TB mỗi bài:       {total_time / max(total_problems, 1):.1f}s")
        print("=" * 60)

        return {
            "summary": summary,
            "results": self.results,
        }

    def save_results(self, output: dict, output_path: Path | str | None = None):
        """Lưu kết quả ra file JSON."""
        if output_path is None:
            output_path = RESULTS_DIR / "baseline_results.json"

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Serialize — bỏ qua các object không JSON-serializable
        def default_serializer(obj):
            if isinstance(obj, (set, frozenset)):
                return list(obj)
            return str(obj)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False,
                      default=default_serializer)

        print(f"\n💾 Kết quả đã lưu tại: {output_path}")


# ---------------------------------------------------------------------------
# Dry-Run Mode (không cần API key)
# ---------------------------------------------------------------------------

def run_dry_mode():
    """
    Chạy thử nghiệm ở chế độ DRY-RUN (không gọi LLM API).
    Sử dụng mã giả định (hardcoded) để minh họa pipeline.
    """
    print("\n" + "=" * 60)
    print("🧪 CHẾ ĐỘ DRY-RUN (không gọi LLM API)")
    print("   Mô phỏng pipeline baseline với mã mẫu hardcoded")
    print("=" * 60)

    # Đọc dataset
    if not DATASET_PATH.exists():
        print(f"❌ Không tìm thấy dataset tại: {DATASET_PATH}")
        return

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    # Mã mẫu hardcoded cho một số bài toán (để demo pipeline)
    sample_solutions = {
        "HE_001": '''
def has_close_elements(numbers, threshold):
    for i in range(len(numbers)):
        for j in range(i + 1, len(numbers)):
            if abs(numbers[i] - numbers[j]) < threshold:
                return True
    return False
''',
        "HE_002": '''
def string_sequence(n):
    return " ".join(str(i) for i in range(n + 1))
''',
        "HE_003": '''
def concatenate(strings):
    return "".join(strings)
''',
        "MB_002": '''
def square_nums(nums):
    return [n ** 2 for n in nums]
''',
    }

    executor = CodeExecutor()
    results = []

    for problem in dataset:
        pid = problem["id"]
        title = problem["title"]
        fn_name = problem["function_name"]
        test_cases = problem["test_cases"]

        print(f"\n{'─'*50}")
        print(f"📌 [{pid}] {title}")

        code = sample_solutions.get(pid)
        if code is None:
            print(f"   ⏭️  Không có mã mẫu hardcoded, bỏ qua.")
            results.append({
                "id": pid, "title": title, "passed_all": None,
                "note": "Skipped — no hardcoded solution in dry-run mode",
            })
            continue

        pass_count = 0
        for i, tc in enumerate(test_cases):
            res = executor.run_test_case(code, fn_name, tc)
            status = "✅" if res["passed"] else "❌"
            print(f"   Test {i+1}: {status}  "
                  f"Input={res['input']}  "
                  f"Expected={res['expected']}  Got={res['actual']}")
            if res["passed"]:
                pass_count += 1

        passed_all = pass_count == len(test_cases)
        print(f"   {'🎉' if passed_all else '⚠️'} "
              f"{pass_count}/{len(test_cases)} tests passed")
        results.append({
            "id": pid, "title": title,
            "passed_all": passed_all,
            "pass_count": pass_count,
            "total_tests": len(test_cases),
        })

    # Tổng kết dry-run
    evaluated = [r for r in results if r.get("passed_all") is not None]
    passed = sum(1 for r in evaluated if r["passed_all"])
    print(f"\n{'='*50}")
    print(f"📊 DRY-RUN: {passed}/{len(evaluated)} bài pass toàn bộ test cases")
    print(f"   (Chỉ đánh giá {len(evaluated)}/{len(results)} bài có mã mẫu)")
    print(f"{'='*50}")


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def main():
    """Entry point chính của Baseline CoT experiment."""
    # Kiểm tra argument dòng lệnh
    if "--dry-run" in sys.argv:
        run_dry_mode()
        return

    # Kiểm tra API key
    if not OPENAI_API_KEY and not OPENROUTER_API_KEY:
        print("⚠️  Không tìm thấy API key.")
        print("   Đặt OPENAI_API_KEY hoặc OPENROUTER_API_KEY trong môi trường,")
        print("   hoặc chạy với --dry-run để thử pipeline không cần API.")
        print()
        print("   Ví dụ:")
        print("     export OPENAI_API_KEY=sk-...")
        print("     python src/baseline_cot.py")
        print()
        print("   Hoặc dry-run:")
        print("     python src/baseline_cot.py --dry-run")
        print()

        # Tự động chuyển sang dry-run
        print("🔄 Tự động chuyển sang chế độ DRY-RUN...\n")
        run_dry_mode()
        return

    # Khởi tạo LLM client
    llm = LLMClient(provider=LLM_PROVIDER, model=MODEL_NAME)

    # Khởi tạo runner
    runner = BaselineCoTRunner(llm_client=llm, dataset_path=DATASET_PATH)

    # Chạy thí nghiệm
    output = runner.run_all()

    # Lưu kết quả
    runner.save_results(output)


if __name__ == "__main__":
    main()
