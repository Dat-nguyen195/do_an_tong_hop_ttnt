"""
SEMSYNTH Lite — Candidate Manager
===================================
Module quản lý tập chương trình ứng viên (candidate programs).

Chức năng chính:
    - Lưu trữ và quản lý Top-K chương trình ứng viên do LLM sinh ra.
    - Lọc (filter) ứng viên dựa trên câu trả lời Đúng/Sai của người dùng.
    - Xếp hạng (rank) ứng viên còn lại.

Lưu ý: Module này là scaffold cho Phase 1.
        Logic chi tiết sẽ được hiện thực đầy đủ ở Phase 2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    """Đại diện cho một chương trình ứng viên."""

    code: str
    """Mã nguồn Python của chương trình."""

    index: int
    """Chỉ số trong danh sách ứng viên ban đầu."""

    score: float = 1.0
    """Điểm xếp hạng (cao hơn = tốt hơn). Mặc định 1.0."""

    is_active: bool = True
    """Còn hoạt động (chưa bị loại) hay không."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Metadata bổ sung (ví dụ: lý do bị loại, kết quả test, ...)."""

    def deactivate(self, reason: str = ""):
        """Đánh dấu ứng viên bị loại."""
        self.is_active = False
        self.metadata["deactivation_reason"] = reason

    def __repr__(self) -> str:
        status = "✅" if self.is_active else "❌"
        return f"Candidate(idx={self.index}, score={self.score:.2f}, {status})"


# ---------------------------------------------------------------------------
# Candidate Manager
# ---------------------------------------------------------------------------

class CandidateManager:
    """
    Quản lý vòng đời của tập chương trình ứng viên.

    Workflow:
        1. add_candidates() — Thêm các ứng viên do LLM sinh ra.
        2. filter_by_answer() — Lọc bớt dựa trên câu trả lời Y/N.
        3. get_active() — Lấy danh sách ứng viên còn hoạt động.
        4. get_best() — Lấy ứng viên tốt nhất.
    """

    def __init__(self):
        self._candidates: list[Candidate] = []
        self._history: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Core Operations
    # ------------------------------------------------------------------

    def add_candidates(self, code_list: list[str]) -> list[Candidate]:
        """
        Thêm danh sách mã nguồn ứng viên.

        Args:
            code_list: Danh sách mã Python do LLM sinh ra.

        Returns:
            Danh sách Candidate objects đã tạo.
        """
        start_idx = len(self._candidates)
        new_candidates = []

        for i, code in enumerate(code_list):
            candidate = Candidate(code=code, index=start_idx + i)
            self._candidates.append(candidate)
            new_candidates.append(candidate)

        self._log_event("add_candidates", {"count": len(code_list)})
        return new_candidates

    def filter_by_answer(
        self,
        question: str,
        answer: bool,
        test_input: dict[str, Any],
        expected_outputs: dict[bool, Any],
    ) -> int:
        """
        Lọc ứng viên dựa trên câu trả lời Đúng/Sai.

        Args:
            question: Câu hỏi ngữ nghĩa đã đặt.
            answer: Câu trả lời của người dùng (True = Yes, False = No).
            test_input: Input dùng để phân biệt hành vi ứng viên.
            expected_outputs: Mapping {True: output_khi_yes, False: output_khi_no}.

        Returns:
            Số ứng viên bị loại.

        Note:
            Logic chi tiết sẽ được hiện thực ở Phase 2.
        """
        # TODO: Phase 2 — Implement filtering logic
        # 1. Chạy mỗi ứng viên active với test_input
        # 2. So sánh output với expected_outputs[answer]
        # 3. Loại ứng viên không khớp

        removed_count = 0
        self._log_event("filter_by_answer", {
            "question": question,
            "answer": answer,
            "removed": removed_count,
        })

        return removed_count

    def filter_by_test(
        self,
        function_name: str,
        test_input: dict[str, Any],
        expected_output: Any,
    ) -> int:
        """
        Lọc ứng viên bằng cách chạy test case trực tiếp.

        Args:
            function_name: Tên hàm cần gọi.
            test_input: Input cho test case.
            expected_output: Output kỳ vọng.

        Returns:
            Số ứng viên bị loại.

        Note:
            Logic chi tiết sẽ được hiện thực ở Phase 2.
        """
        # TODO: Phase 2 — Implement test-based filtering
        removed_count = 0
        self._log_event("filter_by_test", {"removed": removed_count})
        return removed_count

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_active(self) -> list[Candidate]:
        """Lấy danh sách ứng viên còn hoạt động."""
        return [c for c in self._candidates if c.is_active]

    def get_best(self) -> Candidate | None:
        """Lấy ứng viên có điểm cao nhất trong số các ứng viên active."""
        active = self.get_active()
        if not active:
            return None
        return max(active, key=lambda c: c.score)

    @property
    def total_count(self) -> int:
        """Tổng số ứng viên (bao gồm đã loại)."""
        return len(self._candidates)

    @property
    def active_count(self) -> int:
        """Số ứng viên còn hoạt động."""
        return len(self.get_active())

    @property
    def is_converged(self) -> bool:
        """Đã hội tụ (chỉ còn ≤ 1 ứng viên active)."""
        return self.active_count <= 1

    @property
    def history(self) -> list[dict[str, Any]]:
        """Lịch sử các thao tác đã thực hiện."""
        return list(self._history)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _log_event(self, event_type: str, details: dict[str, Any]):
        """Ghi log nội bộ."""
        self._history.append({
            "event": event_type,
            "active_after": self.active_count,
            "details": details,
        })

    def __repr__(self) -> str:
        return (
            f"CandidateManager(total={self.total_count}, "
            f"active={self.active_count})"
        )
