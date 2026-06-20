"""
EpiRAG — Streamlit Frontend
Epidemiological Methodology Assistant

Usage:
    streamlit run frontend/streamlit_app.py
"""

import sys
from pathlib import Path
import streamlit as st

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from app.pipeline import run_pipeline

# --- Page config ---
st.set_page_config(
    page_title="EpiRAG — Epidemiological Methodology Assistant",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS ---
st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: 700;
        color: #1a1a2e;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #555;
        margin-bottom: 2rem;
    }
    .answer-box {
        background-color: #f8f9fa;
        border-left: 4px solid #2c7be5;
        padding: 1.2rem;
        border-radius: 4px;
        margin: 1rem 0;
    }
    .source-tag {
        background-color: #e8f0fe;
        color: #1a73e8;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-size: 0.8rem;
        margin: 0.2rem;
        display: inline-block;
    }
    .chunk-box {
        background-color: #fff;
        border: 1px solid #e0e0e0;
        padding: 0.8rem;
        border-radius: 4px;
        margin: 0.5rem 0;
        font-size: 0.85rem;
    }
    .relevance-high { color: #2e7d32; font-weight: 600; }
    .relevance-mid  { color: #f57c00; font-weight: 600; }
    .relevance-low  { color: #c62828; font-weight: 600; }
    .disclaimer {
        background-color: #fff8e1;
        border-left: 4px solid #ffc107;
        padding: 0.8rem;
        border-radius: 4px;
        font-size: 0.85rem;
        color: #555;
    }
    .footer-note {
        margin-top: 3rem;
        padding-top: 1rem;
        border-top: 1px solid #e0e0e0;
        font-size: 0.8rem;
        color: #888;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


# --- Sidebar ---
with st.sidebar:
    st.markdown("### 🔬 EpiRAG")
    st.markdown("**Epidemiological Methodology Assistant**")
    st.markdown("---")

    st.markdown("#### About")
    st.markdown("""
    EpiRAG helps junior researchers critically evaluate 
    their observational studies by retrieving and 
    synthesizing guidance from canonical epidemiological 
    methodology literature.
    """)

    st.markdown("#### Knowledge Base")
    papers = [
        "Igelström et al. (2022) — causal inference overview",
        "Daniel, De Stavola & Vansteelandt (2016) — causal inference foundations",
        "Tennant et al. (2021) — DAGs & confounders",
        "Anderson et al. (2024) — target trial emulation",
        "Broadbent & Grote (2022) — ML & causal inference",
        "Boscardin et al. (2024) — p-values",
        "Dyer (2025) — variable selection",
        "Inoue et al. (2025) — confounder selection",
        "Penning de Vries & Groenwold (2023) — negative controls",
    ]
    for p in papers:
        st.markdown(f"- {p}")
    st.caption("All sources CC BY 4.0 licensed.")

    st.markdown("---")
    st.markdown("#### Example Questions")
    example_questions = [
        "Is my study causal or descriptive?",
        "What does my p-value actually tell me?",
        "Should I adjust for all correlated variables?",
        "Can I claim causation from this association?",
        "What is confounding and how do I control for it?",
        "What is a DAG and do I need one?",
        "What is a negative control and how does it help detect bias?",
        "What is the difference between a mediator and a confounder?",
    ]
    for q in example_questions:
        if st.button(q, key=q, use_container_width=True):
            st.session_state["prefill_question"] = q

    st.markdown("---")
    st.markdown("""
    <div class='disclaimer'>
    ⚠️ For educational and research purposes only. 
    Does not provide clinical advice. Synthesized from a 
    curated, openly licensed (CC BY 4.0) literature corpus.
    </div>
    """, unsafe_allow_html=True)


# --- Main content ---
st.markdown("<div class='main-header'>🔬 EpiRAG</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='sub-header'>Epidemiological Methodology Assistant, "
    "grounded in Tennant, Igelström, Dyer, and other peer-reviewed, "
    "openly licensed methodology literature</div>",
    unsafe_allow_html=True
)

# --- Evaluation Results ---
st.markdown("#### Evaluation (DeepEval, 27-question pilot)")
eval_cols = st.columns(5)
eval_cols[0].metric("Faithfulness", "0.95", help="How closely answers stick to retrieved sources. Higher is better.")
eval_cols[1].metric("Answer Relevancy", "0.98", help="How directly answers address the question asked. Higher is better.")
eval_cols[2].metric("Contextual Precision", "0.82", help="Relevance of retrieved passages, by rank. Higher is better.")
eval_cols[3].metric("Contextual Recall", "0.77", help="Whether retrieval captured everything needed for a full answer. Higher is better.")
eval_cols[4].metric("Hallucination Rate", "0.27", help="Share of output not supported by source context. Lower is better — this metric is inverted from the others.")
st.caption("Evaluated with DeepEval across 27 synthetic questions. Full methodology in the repo's WRITEUP.md.")
st.markdown("---")

# --- Question input ---
# Handle prefill from sidebar buttons
if "prefill_question" in st.session_state and st.session_state["prefill_question"]:
    st.session_state["question_input"] = st.session_state["prefill_question"]
    st.session_state["prefill_question"] = ""

question = st.text_area(
    "Ask a methodological question about your study:",
    height=100,
    placeholder="e.g. I am running a cohort study on smoking and lung cancer. "
                "Is my research question causal or descriptive? "
                "What do I need to do to make causal claims?",
    key="question_input"
)

agree = st.checkbox(
    "I understand this tool is for educational and research purposes only, "
    "and is not a substitute for expert methodological consultation."
)

col1, col2 = st.columns([1, 5])
with col1:
    ask_button = st.button("Ask", type="primary", use_container_width=True, disabled=not agree)

# --- Run pipeline ---
if ask_button and question.strip():
    if len(question.strip()) < 10:
        st.warning("Please provide a more detailed question.")
    else:
        with st.spinner("Retrieving relevant methodology literature and synthesizing answer..."):
            try:
                result = run_pipeline(question.strip())

                # --- Answer ---
                st.markdown("### Answer")
                st.markdown(
                    f"<div class='answer-box'>{result['answer']}</div>",
                    unsafe_allow_html=True
                )

                # --- Sources ---
                st.markdown("### Sources Used")
                for source in result["sources_short"]:
                    st.markdown(
                        f"<span class='source-tag'>📄 {source}</span>",
                        unsafe_allow_html=True
                    )



            except Exception as e:
                st.error(f"Something went wrong: {str(e)}")

elif ask_button and not question.strip():
    st.warning("Please enter a question.")

# --- Empty state ---
if not question.strip():
    st.markdown("---")
    st.markdown("#### How to use EpiRAG")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        **📋 Describe your study**
        
        Tell the system what kind of data you have, 
        what exposure and outcome you are studying, 
        and what claims you want to make.
        """)
    with col2:
        st.markdown("""
        **❓ Ask your question**
        
        Ask about study design, interpretation, 
        confounding, p-values, adjustment strategy, 
        or whether your claims are supported.
        """)
    with col3:
        st.markdown("""
        **📚 Get grounded answers**
        
        The system retrieves relevant passages from 
        canonical epi methodology literature and 
        synthesizes a cited answer.
        """)

# --- Footer ---
st.markdown(
    "<div class='footer-note'>EpiRAG is a non-commercial educational/research tool. "
    "It synthesizes answers from a curated, openly licensed (CC BY 4.0) epidemiological "
    "methodology corpus. It does not run statistical analyses or access user data, and "
    "should not be treated as a substitute for expert methodological consultation.</div>",
    unsafe_allow_html=True
)