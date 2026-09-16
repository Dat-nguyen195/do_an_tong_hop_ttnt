"""
SEMSYNTH Lite — LLM Client
===========================
Module wrapper quản lý kết nối tới OpenAI API / OpenRouter.
Tải cấu hình từ file .env thông qua python-dotenv.

Sử dụng:
    from src.llm_client import LLMClient

    client = LLMClient()
    response = client.chat("Explain quicksort in Python.")
    code = client.generate_code("Sort a list of integers", "sort_list", "nums")
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Load .env nếu có
# ---------------------------------------------------------------------------

try:
    from dotenv import load_dotenv

    # Tìm file .env ở project root
    _project_root = Path(__file__).resolve().parent.parent
    _env_path = _project_root / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv chưa cài, dùng biến môi trường trực tiếp


# ---------------------------------------------------------------------------
# Configuration Constants
# ---------------------------------------------------------------------------

SUPPORTED_PROVIDERS = ("openai", "openrouter")

PROVIDER_CONFIG = {
    "openai": {
        "env_key": "OPENAI_API_KEY",
        "base_url": None,  # Dùng mặc định của thư viện openai
        "default_model": "gpt-4o-mini",
    },
    "openrouter": {
        "env_key": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "meta-llama/llama-3-70b-instruct",
    },
}


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------

class LLMClient:
    """
    Wrapper thống nhất cho OpenAI-compatible API.

    Hỗ trợ:
        - OpenAI (GPT-4o-mini, GPT-4o, ...)
        - OpenRouter (Llama-3, Mixtral, ...)

    Args:
        provider: "openai" hoặc "openrouter". Mặc định đọc từ LLM_PROVIDER env.
        model: Tên model. Mặc định đọc từ DEFAULT_MODEL env hoặc config.
        api_key: API key. Mặc định đọc từ biến môi trường tương ứng.
        temperature: Nhiệt độ sampling. 0.0 = deterministic.
        max_tokens: Số token tối đa cho response.
    """

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ):
        # Xác định provider
        self.provider = (provider or os.getenv("LLM_PROVIDER", "openai")).lower()
        if self.provider not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Provider '{self.provider}' không được hỗ trợ. "
                f"Chọn một trong: {SUPPORTED_PROVIDERS}"
            )

        config = PROVIDER_CONFIG[self.provider]

        # Xác định model
        self.model = (
            model
            or os.getenv("DEFAULT_MODEL")
            or config["default_model"]
        )

        # Xác định API key
        self.api_key = api_key or os.getenv(config["env_key"], "")
        self.base_url = config["base_url"]

        # Generation parameters
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Lazy-initialized OpenAI client
        self._client = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_client(self):
        """Lazy initialization của OpenAI client."""
        if self._client is not None:
            return self._client

        try:
            from openai import OpenAI
        except ImportError:
            print("❌ Cần cài đặt thư viện openai: pip install openai")
            sys.exit(1)

        if not self.api_key:
            env_var = PROVIDER_CONFIG[self.provider]["env_key"]
            raise ValueError(
                f"Thiếu API key cho provider '{self.provider}'. "
                f"Đặt biến môi trường {env_var} hoặc truyền api_key khi khởi tạo."
            )

        kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url

        self._client = OpenAI(**kwargs)
        return self._client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(
        self,
        user_message: str,
        system_message: str = "You are a helpful assistant.",
        **kwargs,
    ) -> str:
        """
        Gửi một tin nhắn chat đơn giản và nhận phản hồi.

        Args:
            user_message: Nội dung tin nhắn người dùng.
            system_message: System prompt.
            **kwargs: Tham số bổ sung truyền cho API.

        Returns:
            Nội dung text response từ LLM.
        """
        client = self._get_client()

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )

        return response.choices[0].message.content or ""

    def chat_multi(
        self,
        messages: list[dict[str, str]],
        **kwargs,
    ) -> str:
        """
        Gửi cuộc hội thoại nhiều lượt (multi-turn conversation).

        Args:
            messages: Danh sách messages theo format OpenAI
                      [{"role": "system"|"user"|"assistant", "content": "..."}]
            **kwargs: Tham số bổ sung.

        Returns:
            Nội dung text response từ LLM.
        """
        client = self._get_client()

        response = client.chat.completions.create(
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
    ) -> str:
        """
        Sinh mã Python từ mô tả bài toán sử dụng CoT prompting.

        Args:
            description: Mô tả bài toán bằng NL.
            function_name: Tên hàm cần sinh.
            params: Danh sách tham số (dạng chuỗi).
            system_prompt: Custom system prompt (nếu None, dùng mặc định CoT).

        Returns:
            Mã Python đã trích xuất từ code block.
        """
        if system_prompt is None:
            system_prompt = (
                "You are an expert Python programmer. When given a programming task "
                "description, you will:\n"
                "1. Analyze the problem carefully, identifying inputs, outputs, edge "
                "cases, and constraints.\n"
                "2. Think step-by-step about the algorithm and approach.\n"
                "3. Write a complete, correct Python function that solves the problem.\n\n"
                "Return ONLY the Python function code inside a ```python``` code block. "
                "Do not include test cases, examples, or explanations outside the code block."
            )

        user_prompt = (
            f"## Task\n{description}\n\n"
            f"## Function Signature\n```python\ndef {function_name}({params}):\n```\n\n"
            f"## Requirements\n"
            f"- Think step-by-step before writing the code.\n"
            f"- Handle edge cases (empty inputs, single elements, etc.).\n"
            f"- Return the correct output type.\n"
            f"- Write clean, readable Python code.\n\n"
            f"Please provide the complete function implementation."
        )

        raw_response = self.chat(user_prompt, system_message=system_prompt)
        return self._extract_code(raw_response)

    def generate_multiple(
        self,
        description: str,
        function_name: str,
        params: str = "",
        k: int = 5,
    ) -> list[str]:
        """
        Sinh K chương trình ứng viên khác nhau cho cùng một mô tả bài toán.

        Sử dụng temperature > 0 để tạo đa dạng.

        Args:
            description: Mô tả bài toán.
            function_name: Tên hàm.
            params: Tham số.
            k: Số ứng viên cần sinh.

        Returns:
            Danh sách K mã Python.
        """
        candidates = []
        for i in range(k):
            temp = 0.3 + (i * 0.15)  # Tăng dần temperature: 0.3, 0.45, 0.6, ...
            temp = min(temp, 1.0)

            code = self.generate_code(
                description, function_name, params,
            )
            candidates.append(code)

        return candidates

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_code(response: str) -> str:
        """Trích xuất mã Python từ response có markdown code block."""
        if "```python" in response:
            start = response.index("```python") + len("```python")
            end = response.index("```", start)
            return response[start:end].strip()
        elif "```" in response:
            start = response.index("```") + 3
            newline_pos = response.index("\n", start)
            start = newline_pos + 1
            end = response.index("```", start)
            return response[start:end].strip()
        else:
            return response.strip()

    @property
    def is_configured(self) -> bool:
        """Kiểm tra xem client đã có API key chưa."""
        return bool(self.api_key)

    def __repr__(self) -> str:
        masked_key = f"{self.api_key[:8]}..." if len(self.api_key) > 8 else "***"
        return (
            f"LLMClient(provider='{self.provider}', model='{self.model}', "
            f"api_key='{masked_key}')"
        )
