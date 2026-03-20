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
</style>
""",
    unsafe_allow_html=True,
)


# Initialize RAG
@st.cache_resource
def load_rag():
    return FamilyOfficeRAG()


# Header
st.markdown(
    """
<div class="main-header">
    <h1>🏦 Family Office Intelligence Platform</h1>
    <p>Query 220+ verified international family offices 
    using natural language</p>
</div>
""",
    unsafe_allow_html=True,
)

# Sidebar
with st.sidebar:
    st.markdown("### 📊 Dataset Stats")
    st.metric("Total Family Offices", "220+")
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
        if st.button(query, use_container_width=True):
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

query_input = st.text_input(
    "Ask anything about family offices in our database:",
    value=st.session_state.get("query_input", ""),
    placeholder="e.g. Which family offices focus on AI investments with check sizes above $10M?",
    key="query_box",
)

col1, col2 = st.columns([1, 5])
with col1:
    search_clicked = st.button(
        "Search",
        type="primary",
        use_container_width=True,
    )

if search_clicked and query_input:
    with st.spinner("Searching family office intelligence database..."):
        try:
            rag = load_rag()
            result = rag.query(query_input, n_results=n_results)

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
            for source in result["sources"]:
                relevance_color = "🟢" if source["relevance"] >= 70 else "🟡" if source["relevance"] >= 50 else "🔴"
                st.markdown(
                    f'<div class="source-card">{relevance_color} <strong>{source["fo_name"]}</strong> '
                    f'— {source["country"]} | Relevance: {source["relevance"]}% | '
                    f'<a href="{source["website"]}" target="_blank">Visit Website</a></div>',
                    unsafe_allow_html=True,
                )

        except Exception as e:
            st.error(f"Query failed: {str(e)}")
            st.info("Make sure rag_ingest.py has been run first.")

elif search_clicked and not query_input:
    st.warning("Please enter a query first.")

# Footer
st.markdown("---")
st.markdown(
    "*Built with ChromaDB + OpenAI Embeddings + GPT-4o-mini "
    "| Data sourced from Apollo, Hunter, SEC EDGAR*"
)
