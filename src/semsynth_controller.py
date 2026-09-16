"""
SEMSYNTH Lite — Main Controller
=================================
Controller chính điều phối toàn bộ luồng SEMSYNTH:

    Mô tả NL → Sinh Top-K ứng viên → Hỏi Đúng/Sai → Lọc → Kết quả

Workflow:
    1. Nhận mô tả bài toán từ người dùng.
    2. Gọi LLM sinh Top-K chương trình ứng viên.
    3. Phân tích sự khác biệt, sinh câu hỏi Đúng/Sai.
    4. Thu câu trả lời, lọc ứng viên.
    5. Lặp lại (3)–(4) cho đến khi hội tụ.
    6. Trả về mã nguồn tốt nhất.

Lưu ý: Module này là scaffold cho Phase 1.
        Logic chi tiết sẽ được hiện thực đầy đủ ở Phase 2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from src.llm_client import LLMClient
from src.candidate_manager import CandidateManager
from src.question_generator import QuestionGenerator, ClarificationQuestion
from src.code_executor import CodeExecutor


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class SEMSYNTHConfig:
    """Cấu hình cho SEMSYNTH Controller."""

    top_k: int = 5
    """Số chương trình ứng viên sinh ban đầu."""

    max_questions: int = 4
    """Số câu hỏi Đúng/Sai tối đa mỗi bài toán."""

    execution_timeout: int = 5
    """Timeout (giây) khi chạy mã ứng viên."""


# ---------------------------------------------------------------------------
# Session Result
# ---------------------------------------------------------------------------

@dataclass
class SessionResult:
    """Kết quả của một phiên SEMSYNTH."""

    success: bool
    """Có tìm được chương trình phù hợp không."""

    best_code: str | None
    """Mã nguồn tốt nhất (hoặc None nếu thất bại)."""

    questions_asked: list[dict[str, Any]] = field(default_factory=list)
    """Danh sách câu hỏi đã đặt và câu trả lời."""

    total_candidates: int = 0
    """Tổng số ứng viên ban đầu."""

    remaining_candidates: int = 0
    """Số ứng viên còn lại sau khi lọc."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Thông tin bổ sung."""


# ---------------------------------------------------------------------------
# SEMSYNTH Controller
# ---------------------------------------------------------------------------

class SEMSYNTHController:
    """
    Controller chính của SEMSYNTH Lite.

    Điều phối các module:
        - LLMClient: Sinh mã ứng viên.
        - CandidateManager: Quản lý tập ứng viên.
        - QuestionGenerator: Sinh câu hỏi phân biệt.
        - CodeExecutor: Chạy và kiểm thử mã.

    Sử dụng (Phase 2):
        controller = SEMSYNTHController(llm_client)
        result = controller.run(
            description="Sort a list...",
            function_name="sort_list",
            answer_callback=lambda q: input(f"{q} (Y/N): ").lower() == "y"
        )
        print(result.best_code)
    """

    def __init__(
        self,
        llm_client: LLMClient,
        config: SEMSYNTHConfig | None = None,
    ):
        self.llm = llm_client
        self.config = config or SEMSYNTHConfig()
        self.candidate_manager = CandidateManager()
        self.question_generator = QuestionGenerator(
            max_questions=self.config.max_questions
        )
        self.executor = CodeExecutor(timeout=self.config.execution_timeout)

    def run(
        self,
        description: str,
        function_name: str,
        params: str = "",
        answer_callback: Callable[[str], bool] | None = None,
    ) -> SessionResult:
        """
        Chạy phiên SEMSYNTH hoàn chỉnh cho một bài toán.

        Args:
            description: Mô tả bài toán bằng NL.
            function_name: Tên hàm cần sinh.
            params: Danh sách tham số.
            answer_callback: Hàm callback nhận câu hỏi, trả về True/False.
                             Nếu None, sẽ dùng stdin.

        Returns:
            SessionResult chứa mã tốt nhất và metadata.

        Note:
            Sẽ được hiện thực chi tiết ở Phase 2.
        """
        if answer_callback is None:
            answer_callback = self._default_answer_callback

        # TODO: Phase 2 — Implement full SEMSYNTH loop
        # Step 1: Sinh Top-K ứng viên
        # Step 2: Vòng lặp hỏi-đáp
        #   2a. Sinh câu hỏi phân biệt
        #   2b. Thu câu trả lời
        #   2c. Lọc ứng viên
        #   2d. Kiểm tra hội tụ
        # Step 3: Trả kết quả

        return SessionResult(
            success=False,
            best_code=None,
            questions_asked=[],
            total_candidates=0,
            remaining_candidates=0,
            metadata={"note": "Phase 2 — Not yet implemented"},
        )

    @staticmethod
    def _default_answer_callback(question: str) -> bool:
        """Callback mặc định: hỏi người dùng qua stdin."""
        while True:
            answer = input(f"\n❓ {question}\n   (Y)es / (N)o: ").strip().lower()
            if answer in ("y", "yes", "true", "1"):
                return True
            elif answer in ("n", "no", "false", "0"):
                return False
            else:
                print("   ⚠️  Vui lòng trả lời Y hoặc N.")

    def reset(self):
        """Reset trạng thái cho bài toán mới."""
        self.candidate_manager = CandidateManager()
        self.question_generator.reset()
