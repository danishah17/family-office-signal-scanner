import hashlib
import json
import os
import time
from datetime import date

import chromadb
import openai
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

CSV_PATH = "output/family_office_intelligence_master.csv"
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "family_offices"


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


def get_embedding(openai_client, text):
    response = openai_client.embeddings.create(model="text-embedding-3-small", input=text)
    return response.data[0].embedding


def main():
    df = pd.read_csv(CSV_PATH)

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

    # optional reset/upsert safety: delete ids in current set then upsert
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
        embs = [get_embedding(openai_client, t) for t in docs]

        collection.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embs)
        print(f"Embedded batch {b+1}/{total_batches} - Total: {end} records")
        time.sleep(1)

    count = collection.count()
    print(f"ChromaDB ingestion complete - {count} records indexed")

    os.makedirs("docs", exist_ok=True)
    summary = {
        "total_records": count,
        "embedding_model": "text-embedding-3-small",
        "vector_db": "ChromaDB",
        "collection_name": "family_offices",
        "ingestion_date": str(date.today()),
        "chunk_strategy": "full_record_natural_language",
    }
    with open("docs/rag_ingestion_log.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
