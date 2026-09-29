"""Stateful Streamlit demo for SEMSYNTH Lite."""
from __future__ import annotations

import os
import streamlit as st

from src.candidate_manager import CandidateManager
from src.code_executor import CodeExecutor
from src.llm_client import LLMClient, MockLLMClient
from src.question_generator import QuestionGenerator

st.set_page_config(page_title="SEMSYNTH Lite", page_icon="🧪", layout="wide")


def init_state():
    defaults = {
        "manager": None,
        "qgen": None,
        "current_q": None,
        "transcript": [],
        "fn": "",
        "params": "",
        "description": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def next_question():
    manager = st.session_state.manager
    qgen = st.session_state.qgen
    if manager is None or manager.is_converged:
        st.session_state.current_q = None
        return
    st.session_state.current_q = qgen.generate_question(
        manager.get_active(), st.session_state.fn, st.session_state.description,
        params=st.session_state.params,
    )


def answer_current(value: bool):
    q = st.session_state.current_q
    manager = st.session_state.manager
    before = manager.active_count
    removed = manager.filter_by_answer(
        q.question, value,
        yes_candidate_ids=q.yes_candidate_ids,
        no_candidate_ids=q.no_candidate_ids,
    )
    st.session_state.transcript.append({
        "question": q.question,
        "answer": value,
        "before": before,
        "after": manager.active_count,
        "removed": removed,
        "balance": q.balance,
    })
    next_question()


init_state()
st.title("🧪 SEMSYNTH Lite")
st.caption("Behavior-guided semantic clarification for Python program synthesis")

with st.sidebar:
    mode = st.radio("Mode", ["Offline demo (no API key)", "Real LLM"])
    provider = st.selectbox("Provider", ["openai", "openrouter"])
    model = st.text_input("Model", value=os.getenv("DEFAULT_MODEL", "gpt-4o-mini"))
    top_k = st.slider("Top-K", 2, 8, 5)
    max_questions = st.slider("Max questions", 1, 6, 4)
    st.warning("Execution is process-isolated for a research demo, not a hardened multi-tenant sandbox.")

description = st.text_area(
    "Task description",
    value="Remove duplicate elements from a list.",
    height=100,
)
c1, c2 = st.columns(2)
with c1:
    function_name = st.text_input("Function name", value="remove_duplicates")
with c2:
    params = st.text_input("Parameters", value="xs")

if st.button("Generate candidates", type="primary"):
    try:
        llm = MockLLMClient() if mode.startswith("Offline") else LLMClient(provider=provider, model=model)
        executor = CodeExecutor(timeout=5)
        manager = CandidateManager(executor)
        codes = llm.generate_multiple(description, function_name, params, k=top_k)
        manager.add_candidates(list(dict.fromkeys(codes)))
        st.session_state.manager = manager
        st.session_state.qgen = QuestionGenerator(executor, max_questions=max_questions, max_probe_inputs=12)
        st.session_state.transcript = []
        st.session_state.fn = function_name
        st.session_state.params = params
        st.session_state.description = description
        next_question()
    except Exception as exc:
        st.error(f"Could not start synthesis: {type(exc).__name__}: {exc}")

manager = st.session_state.manager
if manager is not None:
    st.metric("Active candidates", f"{manager.active_count}/{manager.total_count}")
    q = st.session_state.current_q
    if q is not None:
        st.subheader("Clarification")
        st.write(q.question)
        st.caption(f"Balanced split score: {q.balance:.3f} · information gain: {q.info_gain:.3f}")
        a, b = st.columns(2)
        a.button("Yes", on_click=answer_current, args=(True,), use_container_width=True)
        b.button("No", on_click=answer_current, args=(False,), use_container_width=True)
    else:
        st.success("No further distinguishing question is available, or the candidates have converged.")

    best = manager.get_best()
    if best:
        st.subheader("Current best candidate")
        st.code(best.code, language="python")

    if st.session_state.transcript:
        st.subheader("Session log")
        st.dataframe(st.session_state.transcript, use_container_width=True)

st.divider()
st.markdown("**Kaggle:** use `kaggle_run.py` for a one-cell smoke demo after cloning the repository.")
