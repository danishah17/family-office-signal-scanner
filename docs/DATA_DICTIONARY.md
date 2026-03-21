# Data dictionary — `family_office_intelligence_master.csv`

Abbreviated reference for reviewers. **Source** indicates primary origin in the build; many fields are merged from several layers.

| Column | Business meaning | Primary source |
|--------|------------------|----------------|
| `fo_name` | Display name of the family office or related entity | Page / Apollo / classifier |
| `fo_type` | SFO vs MFO (or unknown) | Heuristics + text |
| `website` | Canonical site URL | Discovery / Apollo |
| `domain` | Registered domain for dedup + Hunter | Parsed from URL |
| `hq_city`, `hq_country`, `hq_region` | Headquarters | Apollo / inference |
| `year_founded`, `employee_count`, `aum_range` | Firm scale signals | Apollo (when available) |
| `apollo_industry` | Industry tag | Apollo |
| `investment_focus`, `sector_preferences` | Thesis / sector inference | Investment intelligence layer |
| `check_size_range`, `investment_stage` | Deal size and stage | Keywords / inference |
| `geographic_focus`, `co_invest_frequency` | Mandate | Inference |
| `direct_deal_history` | Text signal when present | Various |
| `investment_thesis` | Composed summary line | Pipeline |
| `dm_name_*`, `dm_title_*`, `dm_email_*`, `dm_linkedin_*`, `dm_phone_*` | Up to 3 decision makers | Apollo + Hunter |
| `best_email`, `email_coverage`, `hunter_domain_confidence` | Contact quality | Hunter |
| `linkedin_url` | Org LinkedIn | Apollo |
| `recent_news_headline`, `recent_news_date` | News signal | Scraped / search |
| `recent_filing_type`, `recent_filing_date`, `sec_registered` | SEC / regulatory | SEC EDGAR |
| `completeness_score` | 0–100 internal quality | Pipeline |
| `DATA_TIER` | Tier 1–4 for prioritization | Rules |
| `apollo_enriched` | Whether Apollo returned org payload | Boolean |
| `confidence_score` | Classifier confidence | Heuristic model |
| `description` | Short text blurb | Site / snippet |
| `source_url` | Provenance for the row | Discovery |

For full methodology, see `DATASET_DOCUMENTATION.md`.
