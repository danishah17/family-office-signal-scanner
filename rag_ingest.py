import hashlib
import json
import os
import shutil
import time
from datetime import date
from typing import Optional

import chromadb
import openai
import pandas as pd
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

CSV_PATH = "output/family_office_intelligence_master.csv"
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "family_offices"
OPENAI_EMBED_MODEL = "text-embedding-3-small"
LOCAL_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "60"))


def normalize_text(value):
    if value is None:
        return ""
    s = str(value).strip()
    if s.lower() in {"", "nan", "none"}:
        return ""
    return s


def to_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def build_document(row):
    parts = []

    # Identity
    if row.get("fo_name"):
        parts.append(f"Family Office Name: {row['fo_name']}")
    if row.get("fo_type"):
        parts.append(f"Type: {row['fo_type']}")
    if row.get("hq_city") and row["hq_city"] != "Unknown":
        parts.append(f"Location: {row['hq_city']}, {row.get('hq_country', '')}")
    if row.get("hq_region"):
        parts.append(f"Region: {row['hq_region']}")

    # Investment Profile
    if row.get("investment_focus") and row["investment_focus"] != "Unknown":
        parts.append(f"Investment Focus: {row['investment_focus']}")
    if row.get("sector_preferences") and row["sector_preferences"] != "Unknown":
        parts.append(f"Sector Preferences: {row['sector_preferences']}")
    if row.get("check_size_range") and row["check_size_range"] != "Unknown":
        parts.append(f"Check Size Range: {row['check_size_range']}")
    if row.get("investment_stage") and row["investment_stage"] != "Unknown":
        parts.append(f"Investment Stage: {row['investment_stage']}")
    if row.get("geographic_focus") and row["geographic_focus"] != "Unknown":
        parts.append(f"Geographic Focus: {row['geographic_focus']}")
    if row.get("co_invest_frequency") and row["co_invest_frequency"] != "Unknown":
        parts.append(f"Co-Investment Frequency: {row['co_invest_frequency']}")
    if row.get("aum_range") and row["aum_range"] != "Unknown":
        parts.append(f"AUM Range: {row['aum_range']}")

    # Decision Makers
    for i in range(1, 4):
        name = row.get(f"dm_name_{i}", "")
        title = row.get(f"dm_title_{i}", "")
        email = row.get(f"dm_email_{i}", "")
        if name and str(name) != "nan" and str(name).strip():
            dm_text = f"Decision Maker {i}: {name}"
            if title and str(title) != "nan":
                dm_text += f", {title}"
            if email and str(email) != "nan":
                dm_text += f", Email: {email}"
            parts.append(dm_text)

    # Signals
    if row.get("investment_thesis") and row["investment_thesis"] != "Unknown":
        parts.append(f"Investment Thesis: {row['investment_thesis']}")
    if row.get("recent_news_headline") and str(row["recent_news_headline"]) != "nan":
        parts.append(f"Recent News: {row['recent_news_headline']}")
    if row.get("sec_registered") and str(row["sec_registered"]) == "True":
        parts.append("SEC Registered: Yes")
    if row.get("website"):
        parts.append(f"Website: {row['website']}")

    return " | ".join(parts)


def check_openai_embeddings_working(client: openai.OpenAI) -> bool:
    """Single probe call — must succeed for OpenAI to be the embedding provider."""
    try:
        client.with_options(timeout=OPENAI_TIMEOUT).embeddings.create(
            model=OPENAI_EMBED_MODEL,
            input="embedding connectivity check",
        )
        return True
    except Exception as exc:
        print(
            f"[RAG INGEST] OpenAI embedding probe failed ({exc!r}) — "
            "will not use OpenAI for embeddings."
        )
        return False


def get_embedding(
    text: str,
    openai_client: Optional[openai.OpenAI],
    use_openai: bool,
    local_embedder,
):
    """
    Embeddings: OpenAI text-embedding-3-small when use_openai is True,
    else explicit local sentence-transformers fallback (same model as query path).
    """
    if use_openai and openai_client is not None:
        response = openai_client.with_options(timeout=OPENAI_TIMEOUT).embeddings.create(
            model=OPENAI_EMBED_MODEL,
            input=text,
        )
        return response.data[0].embedding, OPENAI_EMBED_MODEL

    emb = local_embedder.encode(text).tolist()
    return emb, LOCAL_EMBED_MODEL


def resolve_embedding_provider(openai_client: Optional[openai.OpenAI]) -> tuple[bool, str]:
    """
    Returns (use_openai, status_message_printed_at_startup).
    """
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        msg = (
            f"[RAG INGEST] OPENAI_API_KEY not set → using explicit fallback: "
            f"{LOCAL_EMBED_MODEL}"
        )
        print(msg)
        return False, msg

    if openai_client is None:
        print(
            f"[RAG INGEST] OpenAI client unavailable → explicit fallback: {LOCAL_EMBED_MODEL}"
        )
        return False, ""

    if check_openai_embeddings_working(openai_client):
        msg = (
            f"[RAG INGEST] Embedding provider: OpenAI ({OPENAI_EMBED_MODEL}) — key valid."
        )
        print(msg)
        return True, msg

    print(
        f"[RAG INGEST] OPENAI_API_KEY present but embeddings not usable → "
        f"explicit fallback: {LOCAL_EMBED_MODEL}"
    )
    return False, ""


def main():
    # Fresh vector store so ingest/query dimensions always match this run's provider
    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)
        print(f"[RAG INGEST] Removed existing {CHROMA_PATH} for a full rebuild.")

    df = pd.read_csv(CSV_PATH)

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    openai_client = openai.OpenAI(api_key=api_key) if api_key else None
    use_openai, _ = resolve_embedding_provider(openai_client)

    local_embedder = SentenceTransformer(LOCAL_EMBED_MODEL)
    used_embedding_model = ""

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    records = []
    for _, r in df.iterrows():
        row = {k: normalize_text(v) for k, v in r.to_dict().items()}
        doc = build_document(row)
        if len(doc) < 50:
            continue

        domain = normalize_text(row.get("domain")) or normalize_text(row.get("website"))
        if not domain:
            continue
        rec_id = hashlib.md5(domain.encode("utf-8")).hexdigest()

        metadata = {
            "fo_name": normalize_text(row.get("fo_name")),
            "fo_type": normalize_text(row.get("fo_type")),
            "hq_country": normalize_text(row.get("hq_country")),
            "hq_region": normalize_text(row.get("hq_region")),
            "investment_focus": normalize_text(row.get("investment_focus")),
            "check_size_range": normalize_text(row.get("check_size_range")),
            "investment_stage": normalize_text(row.get("investment_stage")),
            "co_invest_frequency": normalize_text(row.get("co_invest_frequency")),
            "email_coverage": normalize_text(row.get("email_coverage")),
            "completeness_score": to_float(row.get("completeness_score"), 0.0),
            "data_tier": normalize_text(row.get("DATA_TIER")),
            "website": normalize_text(row.get("website")),
        }
        records.append((rec_id, doc, metadata))

    total = len(records)
    if total == 0:
        print("No valid records to ingest.")
        return

    batch_size = 20
    total_batches = (total + batch_size - 1) // batch_size

    ids_all = [x[0] for x in records]
    try:
        collection.delete(ids=ids_all)
    except Exception:
        pass

    for b in range(total_batches):
        start = b * batch_size
        end = min(start + batch_size, total)
        batch = records[start:end]
        ids = [x[0] for x in batch]
        docs = [x[1] for x in batch]
        metas = [x[2] for x in batch]
        embs = []
        for t in docs:
            emb, model_name = get_embedding(t, openai_client, use_openai, local_embedder)
            if not used_embedding_model:
                used_embedding_model = model_name
                print(f"[RAG INGEST] First vector used model: {used_embedding_model}")
            embs.append(emb)

        collection.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embs)
        print(f"Embedded batch {b+1}/{total_batches} - Total: {end} records")
        time.sleep(1)

    count = collection.count()
    print(f"ChromaDB ingestion complete - {count} records indexed")

    os.makedirs("docs", exist_ok=True)
    summary = {
        "total_records": count,
        "embedding_model": used_embedding_model or "unknown",
        "vector_db": "ChromaDB",
        "collection_name": COLLECTION_NAME,
        "ingestion_date": str(date.today()),
        "chunk_strategy": "full_record_natural_language",
        "openai_used_for_embeddings": use_openai,
    }
    with open("docs/rag_ingestion_log.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def run_post_ingest_tests():
    """Smoke-test retrieval + generation after a successful ingest."""
    from rag_query import FamilyOfficeRAG

    test_queries = [
        "Which family offices focus on venture capital?",
        "Show me family offices in Europe with emails",
        "Find single family offices in North America",
    ]
    print("\n[RAG INGEST] Running post-ingest test queries...\n")
    rag = FamilyOfficeRAG()
    if not rag.is_database_ready():
        print("[RAG INGEST] Tests skipped: database not ready.")
        return
    for q in test_queries:
        result = rag.query(q)
        ans = result.get("answer") or ""
        print(f"Q: {q}")
        print(f"A: {ans[:200]}{'...' if len(ans) > 200 else ''}")
        src = result.get("sources") or []
        names = [s.get("fo_name", "") for s in src]
        print(f"Sources: {names}")
        print("---")


if __name__ == "__main__":
    main()
    if os.path.isdir(CHROMA_PATH):
        run_post_ingest_tests()
