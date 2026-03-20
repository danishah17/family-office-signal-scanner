import os
import sys

import streamlit as st

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from rag_query import FamilyOfficeRAG

# Page config
st.set_page_config(
    page_title="PolarityIQ Family Office Intelligence",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown(
    """
<style>
    .main-header {
        background: linear-gradient(135deg, #1B2A4A 0%, #2E4A7A 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: #F8F9FA;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #1B2A4A;
    }
    .source-card {
        background: #EEF2FF;
        padding: 0.8rem;
        border-radius: 6px;
        margin: 0.3rem 0;
        font-size: 0.85rem;
    }
    .answer-box {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #E0E0E0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .warn-box {
        background: #FFF8E6;
        border: 1px solid #F0C36D;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        margin: 0.75rem 0;
        color: #5C4A12;
    }
</style>
""",
    unsafe_allow_html=True,
)


# Re-fetch periodically so a fresh ingest is picked up without manual restart
@st.cache_resource(ttl=120)
def load_rag():
    return FamilyOfficeRAG()


# Header
st.markdown(
    """
<div class="main-header">
    <h1>🏦 Family Office Intelligence Platform</h1>
    <p>Query verified international family offices using natural language</p>
</div>
""",
    unsafe_allow_html=True,
)

rag = load_rag()
db_ready = rag.is_database_ready()
db_count = rag.database_count()
status_msg = rag.init_status_message()

# Sidebar
with st.sidebar:
    st.markdown("### 📊 Dataset Stats")
    if db_ready:
        st.metric("Indexed family offices", db_count)
    else:
        st.metric("Indexed family offices", "—")
        st.caption("Index the CSV with `python rag_ingest.py`.")

    st.metric("Countries Covered", "13")
    st.metric("Verified Emails", "38")
    st.metric("Decision Makers", "50+")

    st.markdown("---")
    st.markdown("### 💡 Example Queries")

    example_queries = [
        "Which family offices focus on venture capital?",
        "Show me family offices in Europe with verified emails",
        "Which family offices co-invest frequently?",
        "Find single family offices focused on technology",
        "Which family offices are SEC registered?",
        "Show me family offices in Asia Pacific",
        "Which family offices have check sizes above $25M?",
        "Find multi-family offices in North America",
    ]

    for query in example_queries:
        if st.button(query, use_container_width=True, disabled=not db_ready):
            st.session_state.query_input = query

    st.markdown("---")
    st.markdown("### ⚙️ Settings")
    n_results = st.slider(
        "Records to retrieve",
        min_value=3,
        max_value=10,
        value=5,
    )

# Main query interface
st.markdown("### 🔍 Query the Intelligence Database")

if not db_ready:
    st.error(
        "**Database not initialized.** Run `python rag_ingest.py` from the project root "
        "after `output/family_office_intelligence_master.csv` exists. "
        "This builds `chroma_db/` and indexes embeddings."
    )
    if status_msg:
        st.caption(status_msg)
    st.stop()

query_input = st.text_input(
    "Ask anything about family offices in our database:",
    value=st.session_state.get("query_input", ""),
    placeholder="e.g. Show me family offices in Europe focused on private credit",
    key="query_box",
)

col1, col2 = st.columns([1, 5])
with col1:
    search_clicked = st.button(
        "Search",
        type="primary",
        use_container_width=True,
        disabled=not db_ready,
    )

if search_clicked and query_input:
    with st.spinner("Searching family office intelligence database..."):
        try:
            rag = load_rag()
            result = rag.query(query_input, n_results=n_results)

            if result.get("error") in ("empty_database", "no_collection"):
                st.error(
                    "Database not initialized or empty. Run `rag_ingest.py` first, "
                    "then try again (this page refreshes its connection every ~2 minutes)."
                )
                st.stop()

            if result.get("records_retrieved", 0) == 0:
                st.warning(
                    "No matching records retrieved for this query. "
                    "Try a broader question or different keywords."
                )

            if result.get("weak_match"):
                st.markdown(
                    '<div class="warn-box"><strong>Low relevance match.</strong> '
                    "The closest indexed rows may not answer your question tightly. "
                    "Try one of the suggestions below or rephrase.</div>",
                    unsafe_allow_html=True,
                )
                for sq in result.get("suggested_queries") or []:
                    st.caption(f"• {sq}")

            # Answer
            st.markdown("### 💬 Intelligence Report")
            st.markdown(
                f'<div class="answer-box">{result["answer"]}</div>',
                unsafe_allow_html=True,
            )

            # Metrics row
            st.markdown("---")
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Database Size", f"{result['records_searched']} FOs")
            with m2:
                st.metric("Records Retrieved", result["records_retrieved"])
            with m3:
                st.metric("Query", "✓ Complete")

            # Sources
            st.markdown("### 📋 Source Records")
            if not result.get("sources"):
                st.info(
                    "No source rows attached to this answer — broaden your query or "
                    "check that ingestion used the same embedding provider as this app."
                )
            else:
                for source in result["sources"]:
                    rel = source.get("relevance", 0)
                    relevance_color = "🟢" if rel >= 70 else "🟡" if rel >= 50 else "🔴"
                    site = source.get("website") or ""
                    link = (
                        f'<a href="{site}" target="_blank" rel="noopener">Visit Website</a>'
                        if site
                        else "—"
                    )
                    st.markdown(
                        f'<div class="source-card">{relevance_color} <strong>'
                        f'{source["fo_name"]}</strong> — {source["country"]} | '
                        f'Relevance: {rel}% | {link}</div>',
                        unsafe_allow_html=True,
                    )

        except Exception as e:
            st.error(f"Query failed: {str(e)}")
            st.info("Make sure `rag_ingest.py` has been run and `OPENAI_API_KEY` (optional) is valid.")

elif search_clicked and not query_input:
    st.warning("Please enter a query first.")

# Footer
st.markdown("---")
st.markdown(
    "*Embeddings: OpenAI `text-embedding-3-small` when the key validates, else "
    "`sentence-transformers/all-MiniLM-L6-v2` (must match ingest). "
    "Chat: Anthropic → OpenAI → Gemini → Mistral. "
    "Data: Apollo, Hunter, SEC EDGAR.*"
)
