"""
SEMSYNTH Lite — Tests cho Baseline CoT
========================================
Kiểm thử các thành phần của pipeline Baseline CoT:
    - Dataset loading
    - Code extraction từ markdown
    - Code execution sandbox
    - Pipeline tổng thể (dry-run)
"""

import json
import sys
from pathlib import Path

import pytest

# Thêm project root vào sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.code_executor import CodeExecutor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def executor():
    """Tạo CodeExecutor instance."""
    return CodeExecutor(timeout=5)


@pytest.fixture
def dataset():
    """Tải dataset mẫu."""
    dataset_path = PROJECT_ROOT / "config" / "dataset_sample.json"
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_code_correct():
    """Mã mẫu đúng cho bài toán HE_001 (has_close_elements)."""
    return """
def has_close_elements(numbers, threshold):
    for i in range(len(numbers)):
        for j in range(i + 1, len(numbers)):
            if abs(numbers[i] - numbers[j]) < threshold:
                return True
    return False
"""


@pytest.fixture
def sample_code_wrong():
    """Mã mẫu sai cho bài toán HE_001 (chỉ so sánh kề nhau)."""
    return """
def has_close_elements(numbers, threshold):
    for i in range(len(numbers) - 1):
        if abs(numbers[i] - numbers[i+1]) < threshold:
            return True
    return False
"""


# ---------------------------------------------------------------------------
# Test: Dataset Loading
# ---------------------------------------------------------------------------

class TestDatasetLoading:
    """Kiểm tra tập dữ liệu mẫu."""

    def test_dataset_exists(self):
        """File dataset tồn tại."""
        path = PROJECT_ROOT / "config" / "dataset_sample.json"
        assert path.exists(), f"Dataset file not found: {path}"

    def test_dataset_has_15_problems(self, dataset):
        """Dataset chứa đúng 15 bài toán."""
        assert len(dataset) == 15

    def test_dataset_has_required_fields(self, dataset):
        """Mỗi bài toán có đủ các trường bắt buộc."""
        required_fields = {
            "id", "source", "domain", "title",
            "description", "function_name", "test_cases",
            "clarification_questions",
        }
        for problem in dataset:
            missing = required_fields - set(problem.keys())
            assert not missing, (
                f"Problem {problem.get('id', '?')} thiếu trường: {missing}"
            )

    def test_dataset_domains(self, dataset):
        """Dataset bao phủ cả 2 miền: string và list."""
        domains = {p["domain"] for p in dataset}
        assert "string" in domains, "Thiếu miền 'string'"
        assert "list" in domains, "Thiếu miền 'list'"

    def test_dataset_sources(self, dataset):
        """Dataset có bài từ cả HumanEval và MBPP."""
        sources = {p["source"] for p in dataset}
        assert "HumanEval" in sources, "Thiếu nguồn 'HumanEval'"
        assert "MBPP" in sources, "Thiếu nguồn 'MBPP'"

    def test_each_problem_has_test_cases(self, dataset):
        """Mỗi bài toán có ít nhất 2 test cases."""
        for problem in dataset:
            assert len(problem["test_cases"]) >= 2, (
                f"Problem {problem['id']} có ít hơn 2 test cases"
            )

    def test_each_problem_has_clarification_questions(self, dataset):
        """Mỗi bài toán có ít nhất 1 câu hỏi Đúng/Sai."""
        for problem in dataset:
            assert len(problem["clarification_questions"]) >= 1, (
                f"Problem {problem['id']} thiếu clarification questions"
            )


# ---------------------------------------------------------------------------
# Test: Code Executor
# ---------------------------------------------------------------------------

class TestCodeExecutor:
    """Kiểm tra sandbox chạy mã."""

    def test_execute_correct_code(self, executor, sample_code_correct):
        """Chạy mã đúng phải trả về kết quả chính xác."""
        success, result, error = executor.execute_function(
            sample_code_correct,
            "has_close_elements",
            {"numbers": [1.0, 2.0, 3.0], "threshold": 0.5},
        )
        assert success is True
        assert result is False
        assert error == ""

    def test_execute_returns_true(self, executor, sample_code_correct):
        """Kiểm tra trường hợp trả về True."""
        success, result, _ = executor.execute_function(
            sample_code_correct,
            "has_close_elements",
            {"numbers": [1.0, 2.8, 3.0, 4.0, 5.0, 2.0], "threshold": 0.3},
        )
        assert success is True
        assert result is True

    def test_execute_wrong_function_name(self, executor, sample_code_correct):
        """Gọi hàm không tồn tại phải báo lỗi."""
        success, result, error = executor.execute_function(
            sample_code_correct,
            "nonexistent_function",
            {"x": 1},
        )
        assert success is False
        assert "not found" in error

    def test_execute_syntax_error(self, executor):
        """Mã có lỗi cú pháp phải báo lỗi."""
        bad_code = "def foo(:\n    return 1"
        success, result, error = executor.execute_function(
            bad_code, "foo", {}
        )
        assert success is False
        assert "SyntaxError" in error

    def test_execute_runtime_error(self, executor):
        """Mã có lỗi runtime phải báo lỗi."""
        code = "def foo(x):\n    return 1 / x"
        success, result, error = executor.execute_function(
            code, "foo", {"x": 0}
        )
        assert success is False
        assert "ZeroDivisionError" in error

    def test_run_test_case_pass(self, executor, sample_code_correct):
        """Test case đúng phải passed."""
        tc = {
            "input": {"numbers": [1.0, 2.0, 3.0], "threshold": 0.5},
            "expected_output": False,
        }
        result = executor.run_test_case(
            sample_code_correct, "has_close_elements", tc
        )
        assert result["passed"] is True

    def test_run_test_case_fail(self, executor, sample_code_wrong):
        """Mã sai phải fail trên test case phân biệt."""
        # Mã sai chỉ so sánh kề → không phát hiện 2.8 và 3.0 gần nhau
        # khi chúng không kề nhau trong list gốc
        tc = {
            "input": {"numbers": [1.0, 5.0, 2.0, 2.1], "threshold": 0.5},
            "expected_output": True,
        }
        tc = {
            "input": {"numbers": [1.0, 3.0, 1.1, 5.0], "threshold": 0.2},
            "expected_output": True,
        }
        result = executor.run_test_case(
            sample_code_wrong, "has_close_elements", tc
        )
        assert result["passed"] is False
        assert result["actual"] is False

    def test_run_all_tests(self, executor, sample_code_correct):
        """Chạy tất cả test cases cho mã đúng."""
        test_cases = [
            {
                "input": {"numbers": [1.0, 2.0, 3.0], "threshold": 0.5},
                "expected_output": False,
            },
            {
                "input": {
                    "numbers": [1.0, 2.8, 3.0, 4.0, 5.0, 2.0],
                    "threshold": 0.3,
                },
                "expected_output": True,
            },
        ]
        result = executor.run_all_tests(
            sample_code_correct, "has_close_elements", test_cases
        )
        assert result["passed_all"] is True
        assert result["pass_count"] == 2
        assert result["total"] == 2


# ---------------------------------------------------------------------------
# Test: Code Extraction
# ---------------------------------------------------------------------------

class TestCodeExtraction:
    """Kiểm tra trích xuất mã từ markdown code block."""

    def test_extract_python_block(self):
        """Trích xuất từ ```python ... ```."""
        from src.llm_client import LLMClient

        response = '```python\ndef foo():\n    return 42\n```'
        code = LLMClient._extract_code(response)
        assert "def foo():" in code
        assert "return 42" in code

    def test_extract_generic_block(self):
        """Trích xuất từ ``` ... ```."""
        from src.llm_client import LLMClient

        response = '```\ndef bar(x):\n    return x + 1\n```'
        code = LLMClient._extract_code(response)
        assert "def bar(x):" in code

    def test_extract_no_block(self):
        """Khi không có code block, trả về nguyên văn."""
        from src.llm_client import LLMClient

        response = "def baz():\n    return 0"
        code = LLMClient._extract_code(response)
        assert "def baz():" in code


# ---------------------------------------------------------------------------
# Test: Project Structure
# ---------------------------------------------------------------------------

class TestProjectStructure:
    """Kiểm tra cấu trúc dự án."""

    @pytest.mark.parametrize("path", [
        "src/__init__.py",
        "src/llm_client.py",
        "src/baseline_cot.py",
        "src/candidate_manager.py",
        "src/question_generator.py",
        "src/code_executor.py",
        "src/semsynth_controller.py",
        "tests/__init__.py",
        "tests/test_baseline.py",
        "config/dataset_sample.json",
        "report/README.md",
        "requirements.txt",
        ".env.example",
        ".gitignore",
        "README.md",
        "app.py",
    ])
    def test_file_exists(self, path):
        """Kiểm tra file quan trọng tồn tại."""
        full_path = PROJECT_ROOT / path
        assert full_path.exists(), f"Missing file: {path}"
