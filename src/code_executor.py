"""
SEMSYNTH Lite — Code Executor
==============================
Module sandbox để chạy mã Python ứng viên một cách an toàn
và đánh giá kết quả dựa trên test cases.

Bảo mật:
    - Chạy mã trong namespace cô lập.
    - Có timeout để tránh infinite loop.
    - Deepcopy input trước khi truyền vào hàm.
"""

from __future__ import annotations

import copy
import signal
import sys
from typing import Any


# ---------------------------------------------------------------------------
# Timeout Context Manager (Unix only)
# ---------------------------------------------------------------------------

class TimeoutError(Exception):
    """Exception khi thực thi vượt quá thời gian cho phép."""
    pass


class _Timeout:
    """Context manager cho timeout sử dụng signal (chỉ hoạt động trên Unix)."""

    def __init__(self, seconds: int = 5):
        self.seconds = seconds
        self._supported = hasattr(signal, "SIGALRM")

    def _handler(self, signum, frame):
        raise TimeoutError(f"Execution timed out after {self.seconds}s")

    def __enter__(self):
        if self._supported:
            signal.signal(signal.SIGALRM, self._handler)
            signal.alarm(self.seconds)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._supported:
            signal.alarm(0)
        return False


# ---------------------------------------------------------------------------
# Code Executor
# ---------------------------------------------------------------------------

class CodeExecutor:
    """
    Sandbox chạy mã Python ứng viên và kiểm tra kết quả.

    Sử dụng:
        executor = CodeExecutor(timeout=5)
        result = executor.run_test_case(code, "my_func", test_case)
        print(result["passed"])
    """

    def __init__(self, timeout: int = 5):
        """
        Args:
            timeout: Thời gian tối đa (giây) cho mỗi lần thực thi.
        """
        self.timeout = timeout

    def execute_function(
        self,
        code: str,
        function_name: str,
        test_input: dict[str, Any],
    ) -> tuple[bool, Any, str]:
        """
        Thực thi hàm đã sinh và trả về kết quả.

        Args:
            code: Mã nguồn Python.
            function_name: Tên hàm cần gọi.
            test_input: Dict các tham số đầu vào.

        Returns:
            Tuple (success: bool, result: Any, error_message: str)
        """
        namespace: dict[str, Any] = {}

        try:
            with _Timeout(self.timeout):
                # Thực thi mã để định nghĩa hàm
                exec(code, namespace)  # noqa: S102

                if function_name not in namespace:
                    return (
                        False,
                        None,
                        f"Function '{function_name}' not found in generated code.",
                    )

                func = namespace[function_name]

                # Deepcopy input để tránh side effects
                safe_input = copy.deepcopy(test_input)
                result = func(**safe_input)

                return True, result, ""

        except TimeoutError as e:
            return False, None, str(e)
        except Exception as e:
            return False, None, f"{type(e).__name__}: {e}"

    def run_test_case(
        self,
        code: str,
        function_name: str,
        test_case: dict,
    ) -> dict[str, Any]:
        """
        Chạy một test case và trả về kết quả chi tiết.

        Args:
            code: Mã nguồn Python.
            function_name: Tên hàm.
            test_case: Dict {"input": {...}, "expected_output": ...}

        Returns:
            Dict chứa: passed, input, expected, actual, error
        """
        test_input = test_case["input"]
        expected = test_case["expected_output"]

        success, actual, error = self.execute_function(
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

    def run_all_tests(
        self,
        code: str,
        function_name: str,
        test_cases: list[dict],
    ) -> dict[str, Any]:
        """
        Chạy toàn bộ test cases cho một chương trình.

        Args:
            code: Mã nguồn Python.
            function_name: Tên hàm.
            test_cases: Danh sách test cases.

        Returns:
            Dict chứa: passed_all, pass_count, total, results
        """
        results = []
        pass_count = 0

        for tc in test_cases:
            result = self.run_test_case(code, function_name, tc)
            results.append(result)
            if result["passed"]:
                pass_count += 1

        return {
            "passed_all": pass_count == len(test_cases),
            "pass_count": pass_count,
            "total": len(test_cases),
            "results": results,
        }
