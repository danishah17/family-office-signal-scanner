import html
import os
import sys

import streamlit as st

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from rag_query import FamilyOfficeRAG

# Page config — enterprise: no decorative icon characters
st.set_page_config(
    page_title="PolarityIQ Family Office Intelligence",
    page_icon=None,
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
        white-space: pre-wrap;
        word-wrap: break-word;
    }
    .warn-box {
        background: #FFF8E6;
        border: 1px solid #F0C36D;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        margin: 0.75rem 0;
        color: #5C4A12;
    }
    .rel-high { color: #166534; font-weight: 600; font-size: 0.75rem; }
    .rel-mid { color: #92400E; font-weight: 600; font-size: 0.75rem; }
    .rel-low { color: #991B1B; font-weight: 600; font-size: 0.75rem; }
</style>
""",
    unsafe_allow_html=True,
)


def relevance_label(pct: float) -> tuple[str, str]:
    """Return (css_class, human-readable label) for enterprise UI."""
    if pct >= 70:
        return "rel-high", "High"
    if pct >= 50:
        return "rel-mid", "Medium"
    return "rel-low", "Low"


# Re-fetch periodically so a fresh ingest is picked up without manual restart
@st.cache_resource(ttl=120)
def load_rag():
    return FamilyOfficeRAG()


# Header
st.markdown(
    """
<div class="main-header">
    <h1>Family Office Intelligence Platform</h1>
    <p>Query verified international family offices using natural language.</p>
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
    st.markdown("### Dataset statistics")
    if db_ready:
        st.metric("Indexed family offices", db_count)
    else:
        st.metric("Indexed family offices", "N/A")
        st.caption("Index the CSV with: `python rag_ingest.py`")

    st.metric("Countries covered", "13")
    st.metric("Verified emails (build)", "38")
    st.metric("Decision makers (build)", "50+")

    st.markdown("---")
    st.markdown("### Example queries")

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
    st.markdown("### Settings")
    n_results = st.slider(
        "Records to retrieve",
        min_value=3,
        max_value=10,
        value=5,
    )

# Main query interface
st.markdown("### Query the intelligence database")

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
    "Ask a question about family offices in the database:",
    value=st.session_state.get("query_input", ""),
    placeholder=(
        "Example: Show me family offices in Europe focused on private credit"
    ),
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
    with st.spinner("Searching the intelligence database..."):
        try:
            rag = load_rag()
            result = rag.query(query_input, n_results=n_results)

            if result.get("error") in ("empty_database", "no_collection"):
                st.error(
                    "Database not initialized or empty. Run `rag_ingest.py` first, "
                    "then try again. This page refreshes its connection periodically."
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
                    st.caption(f"- {sq}")

            answer_text = result.get("answer") or ""
            st.markdown("### Intelligence report")
            st.markdown(
                f'<div class="answer-box">{html.escape(answer_text)}</div>',
                unsafe_allow_html=True,
            )

            st.markdown("---")
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Database size", f"{result['records_searched']} records")
            with m2:
                st.metric("Records retrieved", result["records_retrieved"])
            with m3:
                st.metric("Status", "Complete")

            st.markdown("### Source records")
            if not result.get("sources"):
                st.info(
                    "No source rows attached to this answer. Broaden your query or "
                    "confirm that ingestion used the same embedding provider as this app."
                )
            else:
                for source in result["sources"]:
                    rel = float(source.get("relevance", 0) or 0)
                    rel_cls, rel_name = relevance_label(rel)
                    fo = html.escape(str(source.get("fo_name", "Unknown")))
                    country = html.escape(str(source.get("country", "") or ""))
                    site = (source.get("website") or "").strip()
                    if site:
                        safe_href = html.escape(site, quote=True)
                        link = (
                            f'<a href="{safe_href}" target="_blank" '
                            f'rel="noopener noreferrer">Website</a>'
                        )
                    else:
                        link = "No URL"
                    st.markdown(
                        f'<div class="source-card">'
                        f'<span class="{rel_cls}">{rel_name} match ({rel}%)</span><br/>'
                        f"<strong>{fo}</strong> &mdash; {country} | {link}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

        except Exception as e:
            st.error("Query failed. Verify configuration and try again.")
            st.caption(str(e))
            st.info(
                "Ensure `rag_ingest.py` has been run and API keys in Secrets / `.env` "
                "match your chosen embedding provider."
            )

elif search_clicked and not query_input:
    st.warning("Enter a query before searching.")

st.markdown("---")
st.markdown(
    "**Technical note:** Embeddings use OpenAI `text-embedding-3-small` when the key "
    "validates; otherwise `sentence-transformers/all-MiniLM-L6-v2` (must match ingest). "
    "Answer generation: Anthropic, then OpenAI, Gemini, or Mistral as configured. "
    "Enrichment sources: Apollo, Hunter, SEC EDGAR."
)
