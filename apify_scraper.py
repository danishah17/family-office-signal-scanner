import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv


QUERIES = [
    '"family office" "single family office" New York investments',
    '"family office" "single family office" London investments',
    '"family office" "single family office" Singapore investments',
    '"family office" "single family office" Dubai investments',
    '"family office" "single family office" Zurich investments',
    '"family office" "single family office" Hong Kong investments',
    '"family office" "single family office" Toronto investments',
    '"family office" "single family office" Sydney investments',
    '"family office" "single family office" Geneva investments',
    '"family office" "single family office" San Francisco investments',
    '"multi family office" United States wealth management',
    '"multi family office" Europe wealth management',
    '"multi family office" Asia wealth management',
    '"family office" "direct investments" private equity',
    '"family office" venture capital portfolio investments',
    '"family office" real estate investments AUM',
    '"single family office" technology investments',
    '"family office" private credit investments 2024',
    '"family office" infrastructure investments',
    '"family office" "co-investment" opportunities',
]

BLOCKED_URL_PATTERNS = [
    "news.google.com",
    "wikipedia.org",
    "linkedin.com/posts",
    "twitter.com",
    "facebook.com",
    "youtube.com",
    "reddit.com",
    "bloomberg.com/news",
    "reuters.com",
    "wsj.com",
]

APIFY_URL = (
    "https://api.apify.com/v2/acts/apify~google-search-scraper/"
    "run-sync-get-dataset-items"
)


def get_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def is_blocked(url: str) -> bool:
    url_l = (url or "").lower()
    return any(pattern in url_l for pattern in BLOCKED_URL_PATTERNS)


def extract_results(payload_items, query: str):
    extracted = []
    for item in payload_items:
        # The actor may return rows directly or nested under "organicResults".
        if isinstance(item, dict) and isinstance(item.get("organicResults"), list):
            candidates = item["organicResults"]
        else:
            candidates = [item]

        for c in candidates:
            if not isinstance(c, dict):
                continue
            url = c.get("url") or c.get("link") or c.get("displayedUrl") or ""
            title = c.get("title") or ""
            description = c.get("description") or c.get("snippet") or ""
            if not url:
                continue
            extracted.append(
                {
                    "title": title,
                    "url": url,
                    "description": description,
                    "query_used": query,
                }
            )
    return extracted


def main():
    load_dotenv()
    api_key = os.getenv("APIFY_API_KEY")
    if not api_key:
        raise RuntimeError("Missing APIFY_API_KEY in .env")

    Path("raw").mkdir(parents=True, exist_ok=True)
    all_results = []

    headers = {"Authorization": f"Bearer {api_key}"}
    total_queries = len(QUERIES)

    for idx, query in enumerate(QUERIES, start=1):
        body = {
            "queries": query,
            "maxPagesPerQuery": 3,
            "resultsPerPage": 10,
            "outputAsMarkdown": False,
        }
        query_results = []
        try:
            response = requests.post(APIFY_URL, headers=headers, json=body, timeout=180)
            response.raise_for_status()
            data = response.json()
            query_results = extract_results(data, query)

            # filter blocked results
            query_results = [r for r in query_results if not is_blocked(r.get("url", ""))]

            all_results.extend(query_results)
        except Exception as exc:
            print(f"Query {idx}/{total_queries} failed - {exc}")
        finally:
            print(f"Query {idx}/{total_queries} done - Found {len(query_results)} results")
            if idx < total_queries:
                time.sleep(2)

    # Deduplicate by domain, keep the first one seen for each domain.
    deduped = []
    seen_domains = set()
    for row in all_results:
        domain = get_domain(row.get("url", ""))
        if not domain or domain in seen_domains:
            continue
        seen_domains.add(domain)
        deduped.append(row)

    out_path = Path("raw/google_results.json")
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(deduped, f, indent=2, ensure_ascii=False)

    print(f"Total URLs found: {len(deduped)}")
    print(f"Unique domains: {len(seen_domains)}")
    print("Saved to raw/google_results.json")


if __name__ == "__main__":
    main()
