import os
import re
import time
from datetime import datetime

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

APIFY_API_KEY = os.getenv("APIFY_API_KEY")

EDGAR_URL = "https://efts.sec.gov/LATEST/search-index"
APIFY_SEARCH_URL = (
    "https://api.apify.com/v2/acts/apify~google-search-scraper/"
    "run-sync-get-dataset-items"
)
APIFY_HEADERS = {"Authorization": f"Bearer {APIFY_API_KEY}"} if APIFY_API_KEY else {}
SEC_HEADERS = {"User-Agent": "FamilyOfficeResearch research@example.com"}


def s(v):
    if v is None:
        return ""
    return str(v).strip()


def has_value(v):
    val = s(v).lower()
    return val not in {"", "nan", "none", "unknown"}


def classify_investment_profile(text):
    t = s(text).lower()

    focus_map = [
        (["private equity", "buyout", "pe fund"], "Private Equity"),
        (["venture", "startup", "early stage", "seed"], "Venture Capital"),
        (["real estate", "property", "reit", "realty"], "Real Estate"),
        (["private credit", "lending", "debt"], "Private Credit"),
        (["hedge fund", "long/short", "macro"], "Hedge Fund"),
        (["impact", "esg", "sustainable", "green"], "Impact Investing"),
        (["technology", "tech", "software", "saas"], "Technology Focus"),
        (["healthcare", "biotech", "medtech"], "Healthcare Focus"),
        (["infrastructure", "energy", "utilities"], "Infrastructure"),
        (["multi-asset", "diversified", "balanced"], "Multi-Asset"),
    ]
    check_size_map = [
        (["billion", "$1b+", "large cap"], "$100M+"),
        (["hundred million", "$100m", "$500m"], "$25M-$100M"),
        (["million", "$10m", "$50m", "mid market"], "$5M-$25M"),
        (["small", "emerging", "early"], "$1M-$5M"),
    ]
    geo_map = [
        (["global", "international", "worldwide"], "Global"),
        (["north america", "united states", "us market"], "North America"),
        (["europe", "european", "eu"], "Europe Focus"),
        (["asia", "asian", "apac"], "Asia Focus"),
        (["emerging markets", "developing"], "Emerging Markets"),
    ]

    def detect(mapping, default="Unknown"):
        for kws, label in mapping:
            if any(k in t for k in kws):
                return label
        return default

    return {
        "investment_focus": detect(focus_map),
        "check_size_range": detect(check_size_map),
        "geographic_focus": detect(geo_map),
    }


def infer_investment_stage(text):
    t = s(text).lower()
    hits = []
    if any(k in t for k in ["seed", "pre-seed", "angel"]):
        hits.append("Seed/Early")
    if any(k in t for k in ["series a", "series b", "growth equity"]):
        hits.append("Growth")
    if any(k in t for k in ["late stage", "pre-ipo", "mezzanine"]):
        hits.append("Late Stage")
    if any(k in t for k in ["buyout", "acquisition", "control"]):
        hits.append("Buyout")
    if len(hits) > 1:
        return "Multi-Stage"
    return hits[0] if hits else "Unknown"


def infer_coinvest_frequency(text):
    t = s(text).lower()
    if any(k in t for k in ["co-invest", "co-investment", "club deal"]):
        return "High"
    if any(k in t for k in ["selective co-invest", "occasionally"]):
        return "Medium"
    if any(k in t for k in ["sole investor", "lead only"]):
        return "Low"
    return "Unknown"


def extract_aum_hint(text):
    t = s(text)
    patterns = [
        r"\$?\d+(?:\.\d+)?\s?(?:bn|billion|m|million)",
        r"aum[^.,;\n]{0,40}",
    ]
    for p in patterns:
        m = re.search(p, t, flags=re.IGNORECASE)
        if m:
            return m.group(0)[:80]
    return ""


def search_edgar(fo_name):
    params = {
        "q": f'"{fo_name}"',
        "dateRange": "custom",
        "startdt": "2023-01-01",
        "enddt": "2025-12-31",
        "forms": "D,13F-HR,13F-HR/A",
    }
    try:
        resp = requests.get(EDGAR_URL, params=params, headers=SEC_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # EDGAR response shapes vary, so normalize against common keys.
        hits = (
            data.get("hits", {}).get("hits", [])
            or data.get("hits", [])
            or data.get("results", [])
            or []
        )
        if not hits:
            return {
                "recent_filing_type": "",
                "recent_filing_date": "",
                "edgar_aum_hint": "",
                "sec_registered": False,
            }, None

        def filed_at(item):
            src = item.get("_source", item) if isinstance(item, dict) else {}
            dt = src.get("filedAt") or src.get("filed_at") or src.get("periodOfReport") or ""
            try:
                return datetime.fromisoformat(str(dt).replace("Z", ""))
            except Exception:
                return datetime.min

        latest = sorted(hits, key=filed_at, reverse=True)[0]
        src = latest.get("_source", latest) if isinstance(latest, dict) else {}
        filing_type = s(src.get("formType") or src.get("form") or src.get("type"))
        filing_date = s(src.get("filedAt") or src.get("filed_at") or src.get("periodOfReport"))
        text_blob = " ".join(
            [
                s(src.get("displayNames")),
                s(src.get("fileDescription")),
                s(src.get("entityName")),
                s(src.get("adsh")),
            ]
        )
        aum_hint = extract_aum_hint(text_blob)
        sec_registered = bool(hits)

        return {
            "recent_filing_type": filing_type,
            "recent_filing_date": filing_date[:10] if filing_date else "",
            "edgar_aum_hint": aum_hint,
            "sec_registered": sec_registered,
        }, None
    except Exception as exc:
        return (
            {
                "recent_filing_type": "",
                "recent_filing_date": "",
                "edgar_aum_hint": "",
                "sec_registered": False,
            },
            str(exc),
        )
    finally:
        time.sleep(0.5)


def search_news_with_apify(fo_name):
    if not APIFY_API_KEY:
        return {"recent_news_headline": "", "recent_news_date": "", "recent_news_url": ""}, "No APIFY_API_KEY"

    query = f'"{fo_name}" family office 2024 OR 2025 investment'
    payload = {
        "queries": query,
        "maxPagesPerQuery": 1,
        "resultsPerPage": 5,
        "outputAsMarkdown": False,
    }
    try:
        resp = requests.post(APIFY_SEARCH_URL, headers=APIFY_HEADERS, json=payload, timeout=20)
        resp.raise_for_status()
        items = resp.json()
        # Handle direct rows or nested organic results.
        rows = []
        for item in items if isinstance(items, list) else []:
            if isinstance(item, dict) and isinstance(item.get("organicResults"), list):
                rows.extend(item.get("organicResults", []))
            elif isinstance(item, dict):
                rows.append(item)

        if not rows:
            return {"recent_news_headline": "", "recent_news_date": "", "recent_news_url": ""}, None

        first = rows[0]
        return {
            "recent_news_headline": s(first.get("title")),
            "recent_news_date": s(first.get("date"))[:10],
            "recent_news_url": s(first.get("url") or first.get("link")),
        }, None
    except Exception as exc:
        return {"recent_news_headline": "", "recent_news_date": "", "recent_news_url": ""}, str(exc)
    finally:
        time.sleep(1.5)


def build_investment_thesis(fo_type, focus, sector, geo, stage):
    if not any(has_value(v) for v in [fo_type, focus, sector, geo, stage]):
        return ""
    type_phrase = "Single family office" if s(fo_type) == "SFO" else "Multi-family office" if s(fo_type) == "MFO" else "Family office"
    focus_phrase = s(focus).lower() if has_value(focus) else "diversified strategy"
    sector_phrase = s(sector).lower() if has_value(sector) else "multi-sector"
    geo_phrase = s(geo).lower() if has_value(geo) else "regional"
    stage_phrase = s(stage).lower() if has_value(stage) else "flexible"
    return (
        f"{type_phrase} focused on {focus_phrase} with {sector_phrase} sector emphasis, "
        f"{geo_phrase} geographic mandate, and {stage_phrase} stage preference"
    )


def compute_completeness(row):
    score = 0
    if has_value(row.get("fo_name")):
        score += 5
    if s(row.get("fo_type")) in {"SFO", "MFO"}:
        score += 5
    if has_value(row.get("website")):
        score += 5
    if has_value(row.get("hq_city")):
        score += 5
    if has_value(row.get("hq_country")):
        score += 5
    if has_value(row.get("year_founded")):
        score += 3
    if has_value(row.get("aum_range")):
        score += 7
    if has_value(row.get("best_email")):
        score += 10
    if s(row.get("email_coverage")) == "Strong":
        score += 5
    if has_value(row.get("linkedin_url")):
        score += 7
    if has_value(row.get("dm_name_1")):
        score += 8
    if has_value(row.get("dm_name_2")):
        score += 5
    if has_value(row.get("investment_focus")):
        score += 7
    if has_value(row.get("sector_preferences")):
        score += 5
    if has_value(row.get("check_size_range")):
        score += 8
    if has_value(row.get("investment_stage")):
        score += 5
    if has_value(row.get("portfolio_companies")):
        score += 5
    if has_value(row.get("recent_news_headline")):
        score += 3
    if row.get("sec_registered") in {True, False, "True", "False"}:
        score += 3
    if has_value(row.get("investment_thesis")):
        score += 3
    return min(score, 100)


def main():
    in_path = "data/fo_hunter_verified.csv"
    out_path = "data/fo_investment_enriched.csv"
    df = pd.read_csv(in_path)
    total = len(df)

    new_cols = [
        "recent_filing_type",
        "recent_filing_date",
        "edgar_aum_hint",
        "sec_registered",
        "recent_news_headline",
        "recent_news_date",
        "recent_news_url",
        "investment_focus",
        "check_size_range",
        "geographic_focus",
        "investment_stage",
        "co_invest_frequency",
        "sector_preferences",
        "portfolio_companies",
        "investment_thesis",
        "completeness_score",
    ]
    for col in new_cols:
        if col not in df.columns:
            df[col] = ""

    sec_count = 0
    news_count = 0
    focus_count = 0

    for idx, row in df.iterrows():
        fo_name = s(row.get("fo_name")) or s(row.get("domain"))
        if not fo_name:
            continue

        # SEC EDGAR
        sec_data, sec_err = search_edgar(fo_name)
        if sec_err:
            print(f"[{idx+1}/{total}] EDGAR error for {fo_name}: {sec_err}")
        for k, v in sec_data.items():
            df.at[idx, k] = s(v)
        if str(sec_data.get("sec_registered")) == "True":
            sec_count += 1

        # News via Apify
        news_data, news_err = search_news_with_apify(fo_name)
        if news_err and news_err != "No APIFY_API_KEY":
            print(f"[{idx+1}/{total}] Apify news error for {fo_name}: {news_err}")
        for k, v in news_data.items():
            df.at[idx, k] = s(v)
        if has_value(news_data.get("recent_news_headline")):
            news_count += 1

        combined_text = " ".join(
            [
                s(row.get("description")),
                s(row.get("apollo_description")),
                s(news_data.get("recent_news_headline")),
                s(news_data.get("recent_news_url")),
            ]
        )

        profile = classify_investment_profile(combined_text)
        df.at[idx, "investment_focus"] = s(profile["investment_focus"])
        df.at[idx, "check_size_range"] = s(profile["check_size_range"])
        df.at[idx, "geographic_focus"] = s(profile["geographic_focus"])

        # Use focus as sector proxy if no explicit sector.
        sector_pref = s(profile["investment_focus"]) if has_value(profile["investment_focus"]) else "Unknown"
        df.at[idx, "sector_preferences"] = sector_pref

        stage = infer_investment_stage(combined_text)
        coinvest = infer_coinvest_frequency(combined_text)
        df.at[idx, "investment_stage"] = stage
        df.at[idx, "co_invest_frequency"] = coinvest

        if has_value(profile["investment_focus"]):
            focus_count += 1

        thesis = build_investment_thesis(
            row.get("fo_type"),
            profile["investment_focus"],
            sector_pref,
            profile["geographic_focus"],
            stage,
        )
        df.at[idx, "investment_thesis"] = thesis

        # portfolio_companies placeholder from available signal, if present
        if not has_value(df.at[idx, "portfolio_companies"]) and has_value(news_data.get("recent_news_headline")):
            df.at[idx, "portfolio_companies"] = "Signal in news headline"

        # completeness score
        temp_row = df.loc[idx].to_dict()
        score = compute_completeness(temp_row)
        df.at[idx, "completeness_score"] = str(score)

        if (idx + 1) % 10 == 0:
            df = df.astype(str)
            df.to_csv(out_path, index=False)

    df = df.astype(str)
    df.to_csv(out_path, index=False)

    avg_score = pd.to_numeric(df["completeness_score"], errors="coerce").fillna(0).mean()
    focus_pct = (focus_count / total * 100) if total else 0

    print("Investment Intelligence Enrichment Complete")
    print(f"Total processed: {total}")
    print(f"SEC registered found: {sec_count}")
    print(f"News signals found: {news_count}")
    print(f"Investment focus identified: {focus_count} ({focus_pct:.1f}%)")
    print(f"Average completeness score: {avg_score:.1f}")
    print("Saved to data/fo_investment_enriched.csv")


if __name__ == "__main__":
    main()
