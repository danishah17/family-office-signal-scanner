# Changelog

All notable changes to this submission repository are documented here (release-style discipline for reviewers).

## [Unreleased]

### Added
- Committed `chroma_db/` snapshot for Streamlit Cloud RAG demos without server-side ingest.
- `docs/DATA_DICTIONARY.md` — column-level business meanings.
- `docs/TASK4_BUILD_WALKTHROUGH.md` — Task 4 build, stack, ICP, ascension.
- `docs/FALCON_SUBMISSION_PLAYBOOK.md` — official brief alignment (from earlier commit).
- `scripts/smoke_rag.py` — smoke test for RAG DB readiness.
- `.github/workflows/ci.yml` — install deps + smoke test on push/PR.
- `runtime.txt` — Python 3.11 for Streamlit Cloud.

### Changed
- `rag_query.py` — query embeddings aligned with `docs/rag_ingestion_log.json` to prevent OpenAI-vs-local index mismatch.
- `README.md` — architecture diagram, evaluator quickstart, deployment notes.

### Fixed
- Windows-safe logging in RAG scripts (ASCII-only console messages) — prior commits.
