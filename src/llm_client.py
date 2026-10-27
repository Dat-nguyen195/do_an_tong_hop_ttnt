"""Unified LLM client for SEMSYNTH Lite.

The module supports OpenAI-compatible providers and a small deterministic mock
client used by tests/Kaggle smoke demos.  The production client keeps all API
configuration in one place so baselines and SEMSYNTH use the same generation
path.
"""
from __future__ import annotations

import ast
import os
import re
import time
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

SUPPORTED_PROVIDERS = ("openai", "openrouter", "gemini")
PROVIDER_CONFIG = {
    "openai": {
        "env_key": "OPENAI_API_KEY",
        "base_url": None,
        "default_model": "gpt-4o-mini",
    },
    "openrouter": {
        "env_key": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4o-mini",
    },
    "gemini": {
        "env_key": "GEMINI_API_KEY",
        "base_url": None,
        "default_model": "gemini-3.8-flash",
    },
}


class LLMClient:
    """Thin wrapper around an OpenAI-compatible chat-completions API."""

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "openai")).lower()
        if self.provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported provider: {self.provider}")
        config = PROVIDER_CONFIG[self.provider]
        self.model = model or os.getenv("DEFAULT_MODEL") or os.getenv("LLM_MODEL") or config["default_model"]
        self.api_key = api_key or os.getenv(config["env_key"], "")
        self.base_url = config["base_url"]
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.api_key:
            env_var = PROVIDER_CONFIG[self.provider]["env_key"]
            raise ValueError(f"Missing API key. Set {env_var}.")

        if self.provider == "gemini":
            try:
                from google import genai
            except ImportError as exc:
                raise RuntimeError("Install the 'google-genai' package first.") from exc
            self._client = genai.Client(api_key=self.api_key)
            return self._client

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install the 'openai' package first.") from exc
        kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = OpenAI(**kwargs)
        return self._client

    def chat(self, user_message: str, system_message: str = "You are a helpful assistant.", **kwargs) -> str:
        if self.provider == "gemini":
            try:
                from google.genai import types
            except ImportError as exc:
                raise RuntimeError("Install the 'google-genai' package first.") from exc
            response = self._get_client().models.generate_content(
                model=self.model,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=system_message,
                    temperature=kwargs.get("temperature", self.temperature),
                    max_output_tokens=kwargs.get("max_tokens", self.max_tokens),
                ),
            )
            return getattr(response, "text", "") or ""

        response = self._get_client().chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )
        return response.choices[0].message.content or ""

    def chat_multi(self, messages: list[dict[str, str]], **kwargs) -> str:
        if self.provider == "gemini":
            system_parts = [m["content"] for m in messages if m.get("role") == "system"]
            conversation = []
            for m in messages:
                if m.get("role") == "system":
                    continue
                role = m.get("role", "user").upper()
                conversation.append(f"{role}: {m.get('content', '')}")
            return self.chat(
                "\n\n".join(conversation),
                system_message="\n".join(system_parts) or "You are a helpful assistant.",
                **kwargs,
            )

        response = self._get_client().chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )
        return response.choices[0].message.content or ""

    def generate_code(
        self,
        description: str,
        function_name: str,
        params: str = "",
        system_prompt: str | None = None,
        temperature: float | None = None,
        variant_hint: str | None = None,
    ) -> str:
        """Generate one Python function.

        ``temperature`` is explicit so ``generate_multiple`` can actually sample
        diverse candidates; the original project computed temperatures but never
        passed them to the API.
        """
        if system_prompt is None:
            system_prompt = (
                "You are an expert Python programmer. Solve the requested task. "
                "Consider edge cases and plausible interpretations when the wording "
                "is underspecified. Return ONLY one complete Python function inside "
                "a ```python``` block; no tests or prose outside the block."
            )
        diversity = f"\nCandidate diversity instruction: {variant_hint}" if variant_hint else ""
        user_prompt = (
            f"## Task\n{description}\n\n"
            f"## Function Signature\n```python\ndef {function_name}({params}):\n```\n"
            "Implement a clean solution. Do not read files, use the network, spawn "
            "processes, or perform side effects."
            f"{diversity}"
        )
        raw = self.chat(
            user_prompt,
            system_message=system_prompt,
            temperature=self.temperature if temperature is None else temperature,
        )
        code = self._extract_code(raw)
        if not code:
            raise RuntimeError("Empty model response (try increasing max_output_tokens or checking model access)")
        return code

    def generate_multiple(self, description: str, function_name: str, params: str = "", k: int = 5) -> list[str]:
        """Generate up to *k* candidates with real sampling diversity.

        Exact duplicate candidates are de-duplicated.  If the model repeatedly
        emits duplicates, extra attempts are made (bounded to 3*k calls).
        """
        if k < 1:
            return []
        candidates: list[str] = []
        seen: set[str] = set()
        attempt = 0
        failures = 0
        last_error: Exception | None = None
        max_attempts = max(k, 3 * k)
        hints = [
            "prefer the most literal interpretation",
            "consider a reasonable edge-case interpretation",
            "consider an alternative interpretation of ambiguous wording",
            "prefer a concise Pythonic implementation",
            "prefer an explicit implementation with careful boundary handling",
        ]
        while len(candidates) < k and attempt < max_attempts:
            temp = min(0.25 + 0.15 * attempt, 1.0)
            try:
                code = self.generate_code(
                    description,
                    function_name,
                    params,
                    temperature=temp,
                    variant_hint=hints[attempt % len(hints)],
                ).strip()
            except Exception as exc:
                # Retriable provider failures are bounded by the SAME 3*k
                # request budget. No retry for malformed keys or credentials.
                message = str(exc).lower()
                retryable = any(s in message for s in (
                    "429", "500", "502", "503", "504", "timeout", "timed out",
                    "temporarily", "rate limit", "service unavailable",
                    "empty model response"))
                if not retryable:
                    raise
                last_error = exc
                failures += 1
                attempt += 1
                if attempt < max_attempts:
                    time.sleep(min(0.25 * 2 ** min(failures, 4), 4.0))
                continue
            # Whitespace inside string literals and indentation carry meaning.
            # Compare parsed programs, never collapse whitespace in source text.
            try:
                normalized = ast.dump(ast.parse(code), include_attributes=False)
            except SyntaxError:
                normalized = code
            if code and normalized not in seen:
                seen.add(normalized)
                candidates.append(code)
            attempt += 1
        if not candidates and last_error is not None:
            raise RuntimeError(
                f"Provider failed across {attempt} bounded attempts: "
                f"{type(last_error).__name__}: {last_error}"
            ) from last_error
        return candidates

    @staticmethod
    def _extract_code(response: str) -> str:
        match = re.search(r"```(?:python)?\s*(.*?)```", response, re.DOTALL | re.IGNORECASE)
        return (match.group(1) if match else response).strip()

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def __repr__(self) -> str:
        return f"LLMClient(provider={self.provider!r}, model={self.model!r}, configured={self.is_configured})"


class MockLLMClient:
    """Deterministic offline generator for smoke tests and Kaggle demos.

    It intentionally returns multiple plausible implementations for a few common
    ambiguous demo tasks.  It is not used for research measurements.
    """

    provider = "mock"
    model = "offline-demo"
    is_configured = True

    def generate_code(self, description: str, function_name: str, params: str = "", **_: Any) -> str:
        return self.generate_multiple(description, function_name, params, k=1)[0]

    def generate_multiple(self, description: str, function_name: str, params: str = "", k: int = 5) -> list[str]:
        d = description.lower()
        p = params.split(",")[0].strip() or "xs"
        if "duplicate" in d:
            variants = [
                f"def {function_name}({p}):\n    return list(dict.fromkeys({p}))",
                f"def {function_name}({p}):\n    return sorted(set({p}))",
                f"def {function_name}({p}):\n    out=[]\n    for x in {p}:\n        if x not in out:\n            out.append(x)\n    return out",
            ]
        elif "sort" in d:
            variants = [
                f"def {function_name}({p}):\n    return sorted({p})",
                f"def {function_name}({p}):\n    return sorted({p}, reverse=True)",
            ]
        elif "common" in d or "intersection" in d:
            args = [x.strip() for x in params.split(",") if x.strip()]
            a, b = (args + ["a", "b"])[:2]
            variants = [
                f"def {function_name}({a}, {b}):\n    return sorted(set({a}) & set({b}))",
                f"def {function_name}({a}, {b}):\n    return [x for x in {a} if x in {b}]",
            ]
        else:
            variants = [
                f"def {function_name}({params}):\n    return None",
                f"def {function_name}({params}):\n    return False",
                f"def {function_name}({params}):\n    return True",
            ]
        out = []
        while len(out) < k:
            out.extend(variants)
        return out[:k]
