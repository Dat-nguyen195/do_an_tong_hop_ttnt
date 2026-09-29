"""Process-isolated execution for generated Python functions.

This is intentionally described as *process isolation*, not a hardened security
sandbox.  It combines AST policy checks, a fresh temporary working directory,
an isolated Python subprocess and a wall-clock timeout.  Do not expose it as a
multi-tenant arbitrary-code execution service.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from typing import Any

_ALLOWED_IMPORTS = {
    "math", "re", "collections", "itertools", "functools", "heapq", "bisect",
    "statistics", "string", "operator",
}
_FORBIDDEN_CALLS = {
    "open", "exec", "eval", "compile", "input", "breakpoint", "__import__",
}


class UnsafeCodeError(ValueError):
    pass


class _SafetyVisitor(ast.NodeVisitor):
    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.name.split(".")[0] not in _ALLOWED_IMPORTS:
                raise UnsafeCodeError(f"Import '{alias.name}' is not allowed")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        root = (node.module or "").split(".")[0]
        if root not in _ALLOWED_IMPORTS:
            raise UnsafeCodeError(f"Import from '{node.module}' is not allowed")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_CALLS:
            raise UnsafeCodeError(f"Call '{node.func.id}' is not allowed")
        self.generic_visit(node)


_RUNNER = r'''
import json, sys
payload = json.loads(sys.stdin.read())
ns = {"__name__": "__candidate__"}
try:
    exec(payload["code"], ns, ns)
    fn = ns.get(payload["function_name"])
    if not callable(fn):
        raise RuntimeError("Function '%s' not found in generated code." % payload["function_name"])
    value = fn(**payload["test_input"])
    try:
        print(json.dumps({"ok": True, "result": value}, ensure_ascii=False))
    except TypeError:
        print(json.dumps({"ok": True, "result_repr": repr(value)}, ensure_ascii=False))
except Exception as exc:
    print(json.dumps({"ok": False, "error": type(exc).__name__ + ": " + str(exc)}, ensure_ascii=False))
'''


class CodeExecutor:
    def __init__(self, timeout: int = 5):
        self.timeout = timeout

    @staticmethod
    def validate_code(code: str) -> None:
        tree = ast.parse(code)
        _SafetyVisitor().visit(tree)

    def execute_function(self, code: str, function_name: str, test_input: dict[str, Any]) -> tuple[bool, Any, str]:
        try:
            self.validate_code(code)
        except (SyntaxError, UnsafeCodeError) as exc:
            return False, None, f"{type(exc).__name__}: {exc}"
        payload = json.dumps({"code": code, "function_name": function_name, "test_input": test_input}, ensure_ascii=False)
        try:
            with tempfile.TemporaryDirectory(prefix="semsynth_") as tmp:
                proc = subprocess.run(
                    [sys.executable, "-I", "-c", _RUNNER],
                    input=payload,
                    text=True,
                    capture_output=True,
                    cwd=tmp,
                    timeout=self.timeout,
                    env={},
                )
        except subprocess.TimeoutExpired:
            return False, None, f"Execution timed out after {self.timeout}s"
        if proc.returncode != 0:
            return False, None, (proc.stderr.strip() or f"Subprocess exited with code {proc.returncode}")
        line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return False, None, "Candidate produced an invalid execution response"
        if not data.get("ok"):
            return False, None, data.get("error", "Unknown execution error")
        if "result" in data:
            return True, data["result"], ""
        return True, data.get("result_repr"), ""

    def run_test_case(self, code: str, function_name: str, test_case: dict) -> dict[str, Any]:
        success, actual, error = self.execute_function(code, function_name, test_case["input"])
        expected = test_case["expected_output"]
        return {
            "passed": bool(success and actual == expected),
            "input": test_case["input"],
            "expected": expected,
            "actual": actual,
            "error": error if not success else None,
        }

    def run_all_tests(self, code: str, function_name: str, test_cases: list[dict]) -> dict[str, Any]:
        results = [self.run_test_case(code, function_name, tc) for tc in test_cases]
        pass_count = sum(bool(r["passed"]) for r in results)
        return {
            "passed_all": pass_count == len(test_cases),
            "pass_count": pass_count,
            "total": len(test_cases),
            "results": results,
        }
