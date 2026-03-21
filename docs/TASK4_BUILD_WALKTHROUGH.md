# Task 4 — Family Office Signal Scanner (trip-wire product)

## Problem and ICP

- **Pain:** Fundraising and deal teams need a **fast, structured read** on which family offices show *deployment-relevant* signals (mandate fit, timing, outreach angles) before spending hours on manual research.
- **ICP:** Emerging fund managers, placement agents, and BD leads who sell into family offices and need **actionable intelligence** in one sitting—not a raw spreadsheet.

## Price and ascension

- **Trip-wire price point:** Positioned in the Falcon brief range (**$47–$1,000**); exact SKU can be set for GTM (e.g. per-report or per-campaign bundle).
- **Ascension:** Buyers graduate to **full FO data platforms** (e.g. PolarityIQ-style SaaS), **ongoing signal feeds**, or **higher-touch advisory**—the PDF deliverable is the foot in the door.

## What was built

| Layer | Implementation |
|-------|------------------|
| UI | Streamlit (`family-office-signal-scanner/app.py`) |
| Reasoning | Anthropic Claude (model configurable via `ANTHROPIC_MODEL`; validation + fallbacks in `validate_anthropic()`) |
| Structured output | `safe_parse_json()` for fenced / partial JSON from the model |
| Export | ReportLab PDF (`reportlab`) — downloadable report |
| Config | `python-dotenv` / Streamlit Secrets for `ANTHROPIC_API_KEY` |
| XSS hardening | `_esc()` for LLM-sourced HTML snippets |

## How to run locally

```powershell
cd family-office-intelligence
pip install -r family-office-signal-scanner/requirements.txt
streamlit run family-office-signal-scanner/app.py
```

## Streamlit Cloud (second app)

- **Main file:** `family-office-signal-scanner/app.py`
- **Requirements file:** `family-office-signal-scanner/requirements.txt` (Advanced settings)
- **Secrets:** `ANTHROPIC_API_KEY` (required for full flow); optional `ANTHROPIC_MODEL`

## Platforms and tools used

- Python 3.11+, Streamlit, Anthropic API, ReportLab, HTML escaping for safe rendering.

## Failure modes (documented)

- Missing/invalid Anthropic key → user-facing error, no silent mock data.
- Model ID not available on account → cached fallback list in `validate_anthropic()`.
- Malformed JSON from model → `safe_parse_json` returns `None`; UI handles gracefully.
