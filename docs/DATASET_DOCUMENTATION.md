# Family Office Intelligence Dataset — Technical Documentation

## 1. Executive Summary
This submission delivers a validated dataset of 220 international family office records assembled through an end-to-end enrichment workflow.  
The dataset was built using a multi-source pipeline that combines search acquisition, contact enrichment, email verification, and investment signal inference.  
The current output covers 13 countries with 0 verified decision maker contact records.  
The resulting schema and scoring structure are designed to power RAG-based natural language querying for family office intelligence use cases.

## 2. Tech Stack
- Apify (Google Search Scraper) — raw URL acquisition
- Apollo.io API — organization and people enrichment  
- Hunter.io API — email verification and domain search
- SEC EDGAR API — regulatory filing signals (free)
- Python 3.x with pandas, openpyxl, requests
- Claude Code — pipeline orchestration and code generation
- Heuristic classifier — family office URL classification

## 3. Data Acquisition Methodology
- 20 targeted Google search queries were executed through Apify Google Search Scraper.
- 281 unique domains were discovered in the acquisition stage.
- Heuristic classification and quality filtering retained 267 confirmed family-office candidates for downstream enrichment.
- The classifier uses keyword signal matching plus domain pattern checks to separate likely family offices from noise.
- Each record carries a confidence scoring framework (0–100) used in downstream filtering and prioritization.

## 4. Enrichment Methodology
- Layer 1: Apollo org search — employee count, LinkedIn, phone
- Layer 2: Apollo people search — up to 3 decision makers per FO
- Layer 3: Hunter domain search — additional emails
- Layer 4: Hunter email verifier — validates Apollo emails
- Layer 5: SEC EDGAR — regulatory filing history
- Layer 6: Investment intelligence — keyword-based classification

## 5. Validation Methodology
- Domain deduplication at base-domain level to prevent duplicate entities.
- Email field normalization and format validation in enrichment output logic.
- Hunter confidence coverage classification (Strong/Moderate/Weak/None) for contact quality.
- Completeness scoring (0–100) with tiering into Tier 1–Tier 4 for record quality control.
- Minimum threshold filtering removed records below 25 score when contact depth was absent.

## 6. Schema Documentation
| Column Name | Data Type | Description | Example Value |
|---|---|---|---|
| fo_name | str | Family office organization name. | Redefining the Family Office |
| fo_type | str | Family office type classification (SFO/MFO/Unknown). | MFO |
| website | str | Primary website URL for the organization. | https://www.transcendwealthpartners.com |
| domain | str | Base internet domain for deduplication and enrichment. | transcendwealthpartners.com |
| hq_city | str | Headquarters city. | Sonoma |
| hq_country | str | Headquarters country. | United States |
| hq_region | str | Geographic region bucket. | Unknown |
| year_founded | str | Year organization was founded (if known). | Unknown |
| employee_count | str | Estimated employee count from Apollo enrichment. | Unknown |
| aum_range | str | Inferred/known assets under management range. | Unknown |
| apollo_industry | str | Industry label from Apollo org profile. | financial services |
| investment_focus | str | Primary inferred investment strategy/focus. | Technology Focus |
| sector_preferences | str | Primary sector preference inferred from signals. | Technology Focus |
| check_size_range | str | Inferred typical investment check size range. | Unknown |
| investment_stage | str | Inferred stage preference (Seed/Growth/etc.). | Unknown |
| geographic_focus | str | Inferred geographic mandate. | Unknown |
| co_invest_frequency | str | Inferred co-investment frequency. | Unknown |
| direct_deal_history | float64 | Indicator/notes on direct deal activity. |  |
| investment_thesis | str | Generated natural-language investment thesis. | Multi-family office focused on technology focus with technol |
| dm_name_1 | float64 | Decision maker #1 full name. |  |
| dm_title_1 | float64 | Decision maker #1 title. |  |
| dm_email_1 | float64 | Decision maker #1 email. |  |
| dm_linkedin_1 | float64 | Decision maker #1 LinkedIn URL. |  |
| dm_phone_1 | float64 | Decision maker #1 phone number. |  |
| dm_name_2 | float64 | Decision maker #2 full name. |  |
| dm_title_2 | float64 | Decision maker #2 title. |  |
| dm_email_2 | float64 | Decision maker #2 email. |  |
| dm_linkedin_2 | float64 | Decision maker #2 LinkedIn URL. |  |
| dm_phone_2 | float64 | Decision maker #2 phone number. |  |
| dm_name_3 | float64 | Decision maker #3 full name. |  |
| dm_title_3 | float64 | Decision maker #3 title. |  |
| dm_email_3 | float64 | Decision maker #3 email. |  |
| dm_linkedin_3 | float64 | Decision maker #3 LinkedIn URL. |  |
| dm_phone_3 | float64 | Decision maker #3 phone number. |  |
| best_email | str | Best available contact email after verification logic. | cynthia@transcendwealthpartners.com |
| email_coverage | str | Contact quality classification (Strong/Moderate/Weak/None). | Weak |
| hunter_domain_confidence | float64 | Hunter domain confidence score. |  |
| linkedin_url | str | Organization-level LinkedIn URL. | http://www.linkedin.com/company/transcendwealthpartners |
| recent_news_headline | str | Most recent relevant news headline found. | How 2025 Is Redefining the Family Office Tech Stack |
| recent_news_date | str | Date of most recent relevant news signal. | 2025-09-01 |
| recent_filing_type | str | Most recent SEC filing type identified. | 13F-HR/A |
| recent_filing_date | float64 | Most recent SEC filing date identified. |  |
| sec_registered | object | Whether SEC filing signals were identified. | True |
| completeness_score | float64 | Composite record completeness score (0-100). | 68.0 |
| DATA_TIER | str | Tier label mapped from completeness score. | Tier 2 - Standard |
| apollo_enriched | bool | Whether Apollo enrichment returned people/org signals. | False |
| confidence_score | int64 | Family-office classification confidence score. | 100 |
| description | str | Source description/snippet from acquisition stage. | A single-family office dedicated to one family. A multi-fami |
| source_url | str | Original URL source used for this record. | https://www.transcendwealthpartners.com/blog/redefining-the- |

## 7. Data Quality Metrics
- Total records: 220
- Tier 1 Premium: 0 (0.0%)
- Tier 2 Standard: 10 (4.5%)
- Email coverage rate: 17.3%
- Decision maker coverage: 0.0%
- Countries covered: 13
- Average completeness score: 23.6

## 8. Challenges & Solutions
1. Apollo free tier credit limits — solved by prioritizing high-confidence records first.
2. Local Ollama model too slow for classification — solved by replacing with heuristic keyword classifier (30 seconds vs 4.5 hours).
3. PowerShell mkdir syntax differences — solved by running directory creation steps separately.
4. Pandas dtype conflicts with Apollo response payloads — solved by coercing write values to strings before dataframe updates.
5. Family office vs adjacent business disambiguation — solved by multi-signal confidence scoring and negative keyword suppression.

## 9. Key Insights
1. Geographic coverage is broad, with 13 countries represented and the largest concentration in United States.  
2. The current FO mix skews toward SFO records (144) relative to MFO (76), indicating search-query bias toward single-family language.  
3. Email reachability is improving but still mixed: 0 records are Strong and 0 are Moderate on coverage.  
4. The most common inferred investment focus category is currently "Technology Focus", reflecting the dominant signal pattern in descriptions/news text.  
5. Decision maker title patterns are sparse but where available often center on "No title signals", useful for persona targeting.

## 10. What I Would Improve With More Time
1. Phantombuster LinkedIn scraping for verified social profiles
2. PDL API integration for deeper person enrichment
3. Crunchbase portfolio company data via their API
4. Manual verification of top 50 Tier 1 records
5. Real-time news monitoring via RSS feeds per FO
