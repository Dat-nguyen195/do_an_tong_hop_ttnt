"""
SEMSYNTH Lite — Web Demo (Streamlit)
======================================
Giao diện web tương tác cho hệ thống SEMSYNTH Lite.

Chạy:
    streamlit run app.py

Lưu ý: Đây là scaffold cho Phase 1.
        Giao diện đầy đủ sẽ được xây dựng ở Phase 3.
"""

import streamlit as st


# ---------------------------------------------------------------------------
# Page Config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="SEMSYNTH Lite",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🧪 SEMSYNTH Lite")
    st.caption("Interactive Program Synthesis via Semantic Clarification Questions")

    st.divider()

    st.subheader("⚙️ Cấu hình")

    provider = st.selectbox(
        "LLM Provider",
        options=["openai", "openrouter"],
        index=0,
    )

    model = st.text_input(
        "Model",
        value="gpt-4o-mini",
    )

    top_k = st.slider(
        "Số ứng viên (Top-K)",
        min_value=2,
        max_value=10,
        value=5,
    )

    max_questions = st.slider(
        "Số câu hỏi tối đa",
        min_value=1,
        max_value=8,
        value=4,
    )

    st.divider()
    st.markdown(
        "📄 [Phase 1 Report](docs/phase1_report.md)  \n"
        "📊 [Dataset](config/dataset_sample.json)"
    )


# ---------------------------------------------------------------------------
# Main Content
# ---------------------------------------------------------------------------

st.title("🧪 SEMSYNTH Lite")
st.markdown(
    "**Interactive Program Synthesis via Semantic Clarification Questions**"
)

st.info(
    "🚧 **Phase 1 — Scaffold**: Giao diện này đang trong quá trình phát triển. "
    "Chức năng tương tác đầy đủ sẽ có ở Phase 3.",
    icon="ℹ️",
)

# Tab layout
tab_synth, tab_baseline, tab_about = st.tabs([
    "🔬 SEMSYNTH (Interactive)",
    "📊 Baseline CoT",
    "ℹ️ About",
])

# --- Tab 1: SEMSYNTH Interactive ---
with tab_synth:
    st.subheader("Mô tả bài toán")
    description = st.text_area(
        "Nhập mô tả bài toán bằng ngôn ngữ tự nhiên (tiếng Anh):",
        placeholder="Example: Write a function that removes duplicate elements "
                    "from a list while preserving the original order.",
        height=120,
    )

    col1, col2 = st.columns(2)
    with col1:
        function_name = st.text_input(
            "Tên hàm:",
            placeholder="remove_duplicates",
        )
    with col2:
        params = st.text_input(
            "Tham số:",
            placeholder="lst",
        )

    if st.button("🚀 Bắt đầu tổng hợp", type="primary", use_container_width=True):
        st.warning("⚠️ Chức năng này sẽ được hiện thực ở Phase 2–3.")

    st.divider()
    st.subheader("💬 Câu hỏi làm rõ")
    st.caption("Hệ thống sẽ đặt câu hỏi Đúng/Sai tại đây để thu hẹp ứng viên.")

    # Placeholder cho Q&A
    with st.container(border=True):
        st.markdown("*Chưa có câu hỏi. Hãy bắt đầu tổng hợp ở trên.*")

# --- Tab 2: Baseline CoT ---
with tab_baseline:
    st.subheader("📊 Thí nghiệm Baseline CoT")
    st.markdown(
        "Chạy Baseline CoT (0-interaction) trên tập dataset 15 bài toán "
        "để thu thập kết quả đối chứng."
    )

    if st.button("▶️ Chạy Baseline CoT", use_container_width=True):
        st.warning("⚠️ Chức năng này sẽ được tích hợp ở Phase 2–3.")

# --- Tab 3: About ---
with tab_about:
    st.subheader("ℹ️ Về SEMSYNTH Lite")
    st.markdown("""
    **SEMSYNTH Lite** là hệ thống tổng hợp chương trình tương tác, giải quyết
    rào cản **Cognitive Friction Gap** bằng cách:

    1. **Nhận** mô tả bài toán bằng ngôn ngữ tự nhiên
    2. **Sinh** Top-K chương trình ứng viên qua LLM
    3. **Đặt câu hỏi** Đúng/Sai ở mức ngữ nghĩa để phân biệt ứng viên
    4. **Lọc** ứng viên dựa trên câu trả lời
    5. **Trả về** mã Python chính xác nhất

    ### So sánh với các phương pháp khác

    | Phương pháp | Tải nhận thức | Tỷ lệ thành công |
    |---|---|---|
    | PBE (FlashFill) | 🔴 Cao | ~70–80% |
    | Direct LLM | 🟢 Thấp | ~55–65% |
    | Interactive (TiCoder) | 🟡 TB | ~70–80% |
    | **SEMSYNTH Lite** | 🟢 **Rất thấp** | 🎯 **≥75–85%** |

    ### Tech Stack
    - Python 3.10+ · OpenAI API / OpenRouter
    - Streamlit · pytest
    """)
