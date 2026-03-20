# Family Office Intelligence Platform

## A production-grade family office data pipeline, RAG intelligence system, and AI-powered scanner

### Falcon / PolarityIQ evaluation mapping

| Falcon task | Requirement (summary) | Location in repo |
|-------------|-------------------------|------------------|
| **Task 1** | ≥200 real FO records, CSV/XLSX, documentation | `output/`, `docs/DATASET_DOCUMENTATION.md` |
| **Task 2** | RAG on Task 1 data, vector DB, live or recorded demo | `rag_ingest.py`, `rag_query.py`, `app.py`, §11 in dataset doc |
| **Task 3** | SaaS conversion analysis (PolarityIQ) | `docs/` (e.g. analysis PDF / notes) |
| **Task 4** | Trip-wire product ($47–$1k), build + explanation | `family-office-signal-scanner/` |

## Live demos

- **FO Intelligence RAG** (query your dataset): `[YOUR_STREAMLIT_RAG_URL]`
- **Family Office Signal Scanner** (trip-wire product): `[YOUR_STREAMLIT_SCANNER_URL]`

Deploy **two separate** Streamlit Cloud apps: one with root `app.py`, one with `family-office-signal-scanner/app.py` (see [Two Streamlit apps](#two-streamlit-apps-streamlit-cloud)).

---

## Architecture overview

Four-stage pipeline:

1. **Discovery** — Apify Google Search → domain acquisition (`apify_scraper.py`).
2. **Enrichment** — Apollo (org/people), Hunter (domain + verification), optional PDL-style paths (`enrich_apollo.py`, `verify_emails.py`).
3. **Intelligence layer** — SEC EDGAR, news/signals, keyword investment inference (`enrich_investment_intelligence.py`).
4. **RAG system** — ChromaDB + OpenAI `text-embedding-3-small` (or local fallback) + Streamlit UI (`rag_ingest.py`, `rag_query.py`, `app.py`).

The **Signal Scanner** (`family-office-signal-scanner/`) is a **standalone** Streamlit app: Anthropic + ReportLab PDF — it does **not** query Chroma by default.

---

## Dataset stats (reference)

- **220** validated family office records (master output)
- **13** countries covered
- **38** verified emails (within free-tier Hunter constraints during build)
- Multi-source enrichment waterfall (see `docs/DATASET_DOCUMENTATION.md` for honest limits on free tiers)

---

## Task deliverables

| Task | Deliverable |
|------|-------------|
| **Task 1** | Dataset — `output/family_office_intelligence_master.csv` (+ `.xlsx`), `docs/DATASET_DOCUMENTATION.md` |
| **Task 2** | RAG pipeline — `rag_ingest.py`, `rag_query.py`, root `app.py` |
| **Task 3** | SaaS / analysis docs — `docs/` |
| **Task 4** | Signal Scanner — `family-office-signal-scanner/` |

---

## Tech stack

- **Python 3.x**, **pandas**, **openpyxl**
- **Apify**, **Apollo.io**, **Hunter.io**, **SEC EDGAR**
- **ChromaDB**, **OpenAI** embeddings (`text-embedding-3-small`), **sentence-transformers** fallback
- **Anthropic** (RAG chat + Signal Scanner), **Streamlit**
- **ReportLab** (PDF in Signal Scanner)

---

## Setup

```powershell
cd family-office-intelligence
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Edit .env with your keys
```

### Index the dataset for RAG

If `OPENAI_API_KEY` in `.env` is missing or invalid, ingestion uses the local embedding model `sentence-transformers/all-MiniLM-L6-v2` (same as the query path). Fix the key if you want OpenAI embeddings.

```powershell
python rag_ingest.py
```

### Run FO Intelligence (RAG) — repo root

```powershell
streamlit run app.py
```

### Run Family Office Signal Scanner (separate app)

```powershell
streamlit run family-office-signal-scanner/app.py
```

---

## Two Streamlit apps (Streamlit Cloud)

1. **RAG app** — Main file: `app.py` — requires `chroma_db/` after `rag_ingest.py` and `OPENAI_API_KEY` (or local embeddings per `rag_query.py`).
2. **Signal Scanner** — Main file: `family-office-signal-scanner/app.py` — uses `family-office-signal-scanner/requirements.txt` and `family-office-signal-scanner/.streamlit/config.toml`.

Point each Cloud deployment at the **same GitHub repo** but **different entrypoint** and optionally **different secrets** (Scanner only needs Anthropic for the scan flow).

---

## Push & deploy (example)

Replace the remote URL with your GitHub repository.

```powershell
git init
git add .
git commit -m "Family Office Signal Scanner v1.0 — PolarityIQ Trip-Wire Product"
git remote add origin https://github.com/danishah17/family-office-signal-scanner.git
git branch -M main
git push -u origin main
```

*If the repo URL differs, use your actual `git remote`.* Then connect **Streamlit Cloud** (two apps) with the paths in [Two Streamlit apps](#two-streamlit-apps-streamlit-cloud).

---

## Documentation

- **Dataset honesty & methodology:** `docs/DATASET_DOCUMENTATION.md`
- **RAG ingestion log (after ingest):** `docs/rag_ingestion_log.json`

---

## License / usage

Internal / demonstration use unless otherwise specified. Do not commit `.env` or API keys.
