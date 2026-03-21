# Falcon / PolarityIQ — Submission Playbook (Official Brief Alignment)

**Official hand-in:** `optimize@falconscaling.com` — all four tasks in **one** submission; ask for receipt acknowledgement per the PDF.

**How you are judged (from brief):** Top ~1% bar; **human judgment + problem-solving** alongside AI. **Deep, specific thinking** beats generic AI paste. **Honest, working systems with documented limits** beat polished demos that do not work on real data.

---

## Task #1 — Dataset (International Family Office Intelligence)

### Brief requirements
| Requirement | Your repo |
|-------------|-----------|
| **≥200 records** (quality > raw count) | `output/family_office_intelligence_master.csv` (+ `.xlsx` if present) — **220** records |
| **Real-world** (not theoretical) | Master file is the proof artifact |
| **Granularity** (major scoring factor) | Schema: DMs, investment focus, check size, stage, geography, signals, SEC, etc. — see `docs/DATASET_DOCUMENTATION.md` |
| **Documentation:** tech stack, acquisition, enrichment, validation, sources, challenges, insights | `docs/DATASET_DOCUMENTATION.md` (+ regenerate from `generate_documentation.py` if you change stats) |

### Senior-level signals for reviewers
- **Honest § on limits** (free tiers, Hunter/Apollo constraints) — you already frame this; do not oversell.
- **One “schema rationale” paragraph:** why columns exist and how they map to FO research workflows (not just a field list).
- **Reproducibility:** how someone reruns pipeline steps (even if they do not execute all APIs).

### Pre-submit checklist
- [ ] CSV opens cleanly; no broken encoding; row count ≥ 200.
- [ ] Documentation matches file on disk (counts, dates).
- [ ] Optional: short **data dictionary** table (column → business meaning → source).

---

## Task #2 — RAG Pipeline

### Brief requirements
| Requirement | Your repo |
|-------------|-----------|
| Ingest **Task #1 dataset** into a **vector DB** | ChromaDB — `rag_ingest.py`, `./chroma_db` (**committed** for Cloud; parity via `docs/rag_ingestion_log.json`) |
| **Natural language** → **grounded** answers | `rag_query.py` + system prompt; Streamlit `app.py` |
| **≥3 example queries** on **real** data | Post-ingest tests in `rag_ingest.py`; document 3–5 gold queries in README or doc |
| **Live URL** (weighted **above** screen recording) | Two Streamlit Cloud apps — **RAG:** root `app.py` |
| **Documentation:** stack, chunking, embedding, retrieval, failures, improvements | `docs/DATASET_DOCUMENTATION.md` §11 + `docs/rag_ingestion_log.json` |

### Critical brief quote
> A **functional but imperfect** RAG pipeline with **honest documentation of limitations** scores **significantly higher** than a polished demo that **does not** work on your **real** dataset.

**Implication:** Say what breaks (embedding mismatch, sparse DM fields, weak retrieval on niche queries). Show you measured it.

### Production / “senior engineer” signals
- **Explicit embedding policy:** OpenAI `text-embedding-3-small` when key validates; else **same** local model at ingest and query (`sentence-transformers/all-MiniLM-L6-v2`).
- **Index parity:** `rag_query.py` reads `docs/rag_ingestion_log.json` so query embeddings cannot drift from the shipped `chroma_db/` (e.g. valid OpenAI key + MiniLM index).
- **Operational clarity:** `docs/rag_ingestion_log.json` after ingest; README explains rebuild.
- **Security:** No raw LLM HTML in UI without escaping (you used `html.escape` patterns).
- **Streamlit Cloud:** Repo **ships** `chroma_db/`; redeploy after local re-ingest if you change embedding mode.

### Pre-submit checklist
- [ ] Live RAG URL in email + README (replace placeholders).
- [ ] Secrets: `ANTHROPIC_API_KEY` / others in Streamlit Secrets (not repo).
- [ ] 3–5 documented queries with **expected** “grounded” behavior (even if some answers are thin because data is sparse — **say so**).

---

## Task #3 — SaaS Conversion Analysis (PolarityIQ)

### Brief requirements
- Study **https://app.polarityiq.com**
- **Rigorous, evidence-based** plan to improve **free trial → paid** conversion.
- **Highly specific** recommendations — **generic AI copy-paste lowers score.**

### Senior-level approach (what “10 years” looks like)
1. **Actual product time** — sign up / screenshot funnel steps, note friction (signup fields, time-to-value, empty states).
2. **Hypothesis format:** *Observation → Assumption → Test → Metric → Rollback.*
3. **Specific artifacts:** e.g. “Trial day 1 email: subject line A/B,” “in-app checklist: 3 items tied to PolarityIQ modules,” not “improve onboarding.”
4. **Competitive nuance:** how FO data products monetize (seat vs credits vs export) — one paragraph shows domain sense.

### Deliverable
- Prefer a **single PDF or Markdown** in `docs/` (e.g. `docs/TASK3_POLARITYIQ_CONVERSION.md`) linked from README.
- README Task 3 row must point to the **exact file**.

### Pre-submit checklist
- [ ] No generic “add chatbots / leverage AI” fluff without PolarityIQ-specific hooks.
- [ ] Named experiments and success metrics (conversion rate, activation, PQL).

---

## Task #4 — Trip-Wire Product ($47–$1,000)

### Brief requirements
- **Pain point**, **ICP**, **price**, **ascension path**
- **Not a pitch deck** — something a **real investor could purchase today**
- **Step-by-step build** + platforms used

### Your build
- **`family-office-signal-scanner/`** — Streamlit + Anthropic + ReportLab PDF; aligned FO “signal” niche.
- Second Streamlit Cloud app: main file `family-office-signal-scanner/app.py`, requirements `family-office-signal-scanner/requirements.txt`.

### Senior-level signals
- **Pricing rationale** in README (why $X fits ICP and ascends to PolarityIQ / data SKUs).
- **Ascension diagram** (Mermaid in README): Trip-wire → SaaS / higher data products.
- **Operational:** model ID configurable; JSON parsing hardened; errors enterprise-toned.

### Pre-submit checklist
- [ ] Live Scanner URL in email + README.
- [ ] `TASK4_BUILD_WALKTHROUGH.md` (or section in README): stack, prompts, PDF gen, failure handling.

---

## Repository & Delivery (Cross-Cutting “Enterprise” Bar)

### What distinguishes senior work
| Dimension | Junior + AI vibe | Senior / production vibe |
|-----------|-------------------|---------------------------|
| Docs | Buzzwords | Tradeoffs, limits, metrics, runbooks |
| RAG | “It works” | Ingest log, embedding policy, failure modes |
| Task 3 | Generic growth hacks | Product-specific, testable hypotheses |
| Code | Secrets in repo | `.env.example`, Streamlit Secrets, gitignore |
| Submission | Link dump | One email, numbered deliverables, ack requested |

### Suggested README upgrades (optional but high leverage)
- **Architecture diagram** (Mermaid): data → enrich → CSV → Chroma → Streamlit.
- **“Evaluator quickstart”** — 60 seconds: open CSV, open two URLs, run 3 queries.
- **CHANGELOG.md** or release tag for submission snapshot.

---

## Risk Register (Be Ahead of Reviewers)

| Risk | Mitigation |
|------|------------|
| RAG empty on Cloud | Repo ships `chroma_db/`; optional re-ingest documented in README |
| Invalid API keys in `.env` | Fix before demo; Cloud uses Secrets only |
| Task 3 feels AI-generic | Rewrite with PolarityIQ-specific observations |
| Dataset stats drift | Regenerate doc from `generate_documentation.py` |

---

*This playbook is derived from the official 72-hour Falcon / PolarityIQ differentiator brief. Keep it next to `README.md` for submission week.*
