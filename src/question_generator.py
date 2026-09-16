"""
SEMSYNTH Lite — Question Generator
====================================
Module sinh câu hỏi ngữ nghĩa Đúng/Sai (Semantic Yes/No Questions)
để phân biệt các chương trình ứng viên.

Chiến lược:
    - Greedy Disambiguation: Chọn câu hỏi phân chia tập ứng viên đều nhất (~50/50).
    - Semantic-Level: Câu hỏi về hành vi chương trình, không phải cú pháp.

Lưu ý: Module này là scaffold cho Phase 1.
        Logic chi tiết sẽ được hiện thực đầy đủ ở Phase 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ClarificationQuestion:
    """Đại diện cho một câu hỏi làm rõ ngữ nghĩa."""

    question: str
    """Nội dung câu hỏi dạng NL (tiếng Anh)."""

    test_input: dict[str, Any]
    """Input phân biệt (distinguishing input) dùng để tách nhóm ứng viên."""

    expected_outputs: dict[str, Any]
    """Mapping: {"yes": output_nếu_Yes, "no": output_nếu_No}."""

    info_gain: float = 0.0
    """Lượng thông tin kỳ vọng thu được (information gain). Cao hơn = tốt hơn."""

    def __repr__(self) -> str:
        return (
            f"ClarificationQuestion(gain={self.info_gain:.3f}, "
            f"q='{self.question[:50]}...')"
        )


# ---------------------------------------------------------------------------
# Question Generator
# ---------------------------------------------------------------------------

class QuestionGenerator:
    """
    Sinh câu hỏi ngữ nghĩa Đúng/Sai để phân biệt các ứng viên.

    Workflow:
        1. Phân tích sự khác biệt hành vi giữa các ứng viên.
        2. Tìm distinguishing input (input mà các ứng viên cho output khác nhau).
        3. Sinh câu hỏi NL dựa trên sự khác biệt đó.
        4. Chọn câu hỏi có information gain cao nhất.

    Note:
        Logic chi tiết sẽ được hiện thực ở Phase 2.
    """

    def __init__(self, max_questions: int = 5):
        """
        Args:
            max_questions: Số câu hỏi tối đa cho mỗi bài toán.
        """
        self.max_questions = max_questions
        self._questions_asked: list[ClarificationQuestion] = []

    def generate_question(
        self,
        candidates: list[Any],
        function_name: str,
        description: str,
    ) -> ClarificationQuestion | None:
        """
        Sinh câu hỏi phân biệt tốt nhất cho tập ứng viên hiện tại.

        Args:
            candidates: Danh sách Candidate objects còn active.
            function_name: Tên hàm.
            description: Mô tả bài toán gốc.

        Returns:
            ClarificationQuestion hoặc None nếu không cần hỏi thêm.

        Note:
            Sẽ được hiện thực chi tiết ở Phase 2.
        """
        # Kiểm tra điều kiện dừng
        if len(candidates) <= 1:
            return None

        if len(self._questions_asked) >= self.max_questions:
            return None

        # TODO: Phase 2 — Implement question generation logic
        # 1. Tạo distinguishing inputs
        # 2. Chạy mỗi ứng viên, phân nhóm theo output
        # 3. Dùng LLM sinh câu hỏi NL từ sự khác biệt
        # 4. Tính information gain, chọn câu hỏi tối ưu

        return None

    @property
    def questions_asked(self) -> list[ClarificationQuestion]:
        """Danh sách câu hỏi đã đặt."""
        return list(self._questions_asked)

    @property
    def questions_remaining(self) -> int:
        """Số câu hỏi còn có thể đặt."""
        return max(0, self.max_questions - len(self._questions_asked))

    def reset(self):
        """Reset trạng thái cho bài toán mới."""
        self._questions_asked = []
