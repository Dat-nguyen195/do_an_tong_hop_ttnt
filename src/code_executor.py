"""Process-isolated execution for generated Python functions.

This is intentionally described as *process isolation*, not a hardened security
sandbox.  It combines AST policy checks, a fresh temporary working directory,
an isolated Python subprocess and a wall-clock timeout.  Do not expose it as a
multi-tenant arbitrary-code execution service.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
from collections import OrderedDict
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
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
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

    def visit_Name(self, node: ast.Name):
        if node.id == "__builtins__" or node.id.startswith("__"):
            raise UnsafeCodeError(f"Name '{node.id}' is not allowed")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if node.attr.startswith("__"):
            raise UnsafeCodeError(f"Attribute '{node.attr}' is not allowed")
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


_BATCH_RUNNER = r'''
import json, sys
payload = json.loads(sys.stdin.read())
results = []
for test_input in payload["test_inputs"]:
    try:
        ns = {"__name__": "__candidate__"}
        exec(payload["code"], ns, ns)
        fn = ns.get(payload["function_name"])
        if not callable(fn):
            raise RuntimeError("Function '%s' not found in generated code." % payload["function_name"])
        value = fn(**test_input)
        try:
            result = {"ok": True, "result": value}
            json.dumps(result)
        except (TypeError, ValueError):
            result = {"ok": True, "result_repr": repr(value)}
        results.append(result)
    except Exception as exc:
        results.append({"ok": False, "error": type(exc).__name__ + ": " + str(exc)})
print(json.dumps(results, ensure_ascii=False))
'''


class CodeExecutor:
    """Isolated executor with a bounded, per-instance deterministic memo cache.

    Cache only when candidates are pure/deterministic. Turn off caching for
    stochastic or time-dependent generated functions.
    """
    def __init__(self, timeout: int = 5, cache_size: int = 2048, enable_cache: bool = True):
        self.timeout = timeout
        self.cache_size = max(0, cache_size) if enable_cache else 0
        self._cache: OrderedDict[str, tuple[bool, Any, str]] = OrderedDict()
        self.cache_hits = 0
        self.cache_misses = 0
        self.subprocess_calls = 0

    @property
    def stats(self) -> dict[str, int]:
        return {"hits": self.cache_hits, "misses": self.cache_misses,
                "subprocess_calls": self.subprocess_calls, "entries": len(self._cache)}

    @staticmethod
    def validate_code(code: str) -> None:
        tree = ast.parse(code)
        _SafetyVisitor().visit(tree)

    def execute_function(self, code: str, function_name: str, test_input: dict[str, Any]) -> tuple[bool, Any, str]:
        try:
            self.validate_code(code)
        except (SyntaxError, UnsafeCodeError) as exc:
            return False, None, f"{type(exc).__name__}: {exc}"
        try:
            payload = json.dumps({"code": code, "function_name": function_name, "test_input": test_input}, ensure_ascii=False)
        except TypeError as exc:
            return False, None, f"Test input is not JSON serializable: {exc}"
        key = hashlib.sha256((str(self.timeout) + "\0" + payload).encode("utf-8")).hexdigest()
        if self.cache_size and key in self._cache:
            self.cache_hits += 1
            self._cache.move_to_end(key)
            return copy.deepcopy(self._cache[key])
        self.cache_misses += 1
        self.subprocess_calls += 1
        try:
            with tempfile.TemporaryDirectory(prefix="semsynth_") as tmp:
                proc = subprocess.run(
                    [sys.executable, "-I", "-X", "utf8", "-c", _RUNNER],
                    input=payload,
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                    cwd=tmp,
                    # Startup overhead can be substantial on oversubscribed
                    # Kaggle CPU workers; preserve an execution budget with a
                    # small launch grace rather than flaky 1-second probes.
                    timeout=self.timeout + 2.0,
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
            result = (False, None, data.get("error", "Unknown execution error"))
        elif "result" in data:
            result = (True, data["result"], "")
        else:
            result = (True, data.get("result_repr"), "")
        if self.cache_size:
            self._cache[key] = copy.deepcopy(result)
            if len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)
        return result

    def execute_batch(self, code: str, function_name: str,
                      inputs: list[dict[str, Any]]) -> list[tuple[bool, Any, str]]:
        """Evaluate many independent probes in one isolated Python process.

        The code is re-executed with a fresh namespace for each input. Each
        probe is memoized identically to execute_function; timeout covers the
        entire batch. Not a hardened sandbox for untrusted adversarial code.
        """
        if not inputs:
            return []
        try:
            self.validate_code(code)
        except (SyntaxError, UnsafeCodeError) as exc:
            return [(False, None, f"{type(exc).__name__}: {exc}")] * len(inputs)
        results: list[tuple[bool, Any, str] | None] = [None] * len(inputs)
        uncached: list[tuple[int, dict[str, Any], str]] = []
        for i, inp in enumerate(inputs):
            try:
                payload = json.dumps({"code": code, "function_name": function_name,
                                      "test_input": inp}, ensure_ascii=False)
            except TypeError as exc:
                results[i] = (False, None, f"Test input is not JSON serializable: {exc}")
                continue
            key = hashlib.sha256((str(self.timeout) + "\0" + payload).encode("utf-8")).hexdigest()
            if self.cache_size and key in self._cache:
                self.cache_hits += 1
                self._cache.move_to_end(key)
                results[i] = copy.deepcopy(self._cache[key])
            else:
                uncached.append((i, inp, key))
        if uncached:
            self.cache_misses += len(uncached)
            self.subprocess_calls += 1
            payload = json.dumps({"code": code, "function_name": function_name,
                                  "test_inputs": [inp for _, inp, _ in uncached]}, ensure_ascii=False)
            try:
                with tempfile.TemporaryDirectory(prefix="semsynth_batch_") as tmp:
                    proc = subprocess.run(
                        [sys.executable, "-I", "-X", "utf8", "-c", _BATCH_RUNNER], input=payload,
                        text=True, encoding="utf-8", capture_output=True, cwd=tmp,
                        timeout=self.timeout * len(uncached) + 2.0, env={},
                    )
                if proc.returncode:
                    raise RuntimeError(proc.stderr.strip() or f"Exit code {proc.returncode}")
                data = json.loads(proc.stdout.strip().splitlines()[-1])
                if len(data) != len(uncached):
                    raise RuntimeError("Incorrect batch response count")
                batch = [(True, d.get("result", d.get("result_repr")), "") if d.get("ok")
                         else (False, None, d.get("error", "Unknown error")) for d in data]
            except (subprocess.TimeoutExpired, RuntimeError, ValueError, IndexError) as exc:
                batch = [(False, None, f"Batch execution failed: {type(exc).__name__}: {exc}")] * len(uncached)
            for (i, _, key), value in zip(uncached, batch):
                results[i] = value
                if self.cache_size:
                    self._cache[key] = copy.deepcopy(value)
                    if len(self._cache) > self.cache_size:
                        self._cache.popitem(last=False)
        return [value for value in results if value is not None]

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
            "passed_all": bool(test_cases) and pass_count == len(test_cases),
            "pass_count": pass_count,
            "total": len(test_cases),
            "results": results,
        }
