import csv
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

# Keywords that strongly indicate a real family office website
FO_POSITIVE_KEYWORDS = [
    "family office",
    "familyoffice",
    "family-office",
    "wealth management",
    "private wealth",
    "investment office",
    "multi-family",
    "single family",
    "generational wealth",
    "private investment",
    "family investments",
    "family capital",
    "patrimony",
    "family fund",
    "private capital",
]

# Keywords that indicate it is NOT a family office website
FO_NEGATIVE_KEYWORDS = [
    "law firm",
    "accounting",
    "consultant",
    "software",
    "real estate agent",
    "insurance",
    "bank branch",
    "news",
    "article",
    "blog post",
    "wikipedia",
    "linkedin.com/in/",
    "crunchbase",
    "pitchbook",
    "job listing",
    "careers",
    "glassdoor",
    "indeed",
]

# Known FO domain patterns
FO_DOMAIN_PATTERNS = [
    r".*capital.*",
    r".*wealth.*",
    r".*family.*",
    r".*office.*",
    r".*invest.*",
    r".*asset.*",
    r".*partners.*",
    r".*holdings.*",
    r".*ventures.*",
    r".*management.*",
    r".*equity.*",
    r".*fund.*",
]


def extract_domain(url):
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return None


def get_base_url(url):
    try:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        return url


def classify_family_office(title, description, url, domain):
    title_lower = (title or "").lower()
    desc_lower = (description or "").lower()
    domain_lower = (domain or "").lower()
    combined = f"{title_lower} {desc_lower} {domain_lower}"

    # Hard negative filter
    for neg in FO_NEGATIVE_KEYWORDS:
        if neg in combined:
            return False, "Unknown", 0

    # Count positive signals
    positive_hits = sum(1 for kw in FO_POSITIVE_KEYWORDS if kw in combined)

    # Domain pattern match
    domain_match = any(re.match(p, domain_lower) for p in FO_DOMAIN_PATTERNS)

    # Determine FO type
    fo_type = "Unknown"
    if "multi" in combined or "mfo" in combined:
        fo_type = "MFO"
    elif "single" in combined or "sfo" in combined:
        fo_type = "SFO"
    elif "family office" in combined:
        fo_type = "SFO"  # default assumption

    # Calculate confidence
    confidence = 0
    if "family office" in combined:
        confidence += 50
    if positive_hits >= 2:
        confidence += 20
    if domain_match:
        confidence += 15
    if fo_type != "Unknown":
        confidence += 15

    is_fo = confidence >= 55
    return is_fo, fo_type, confidence


def extract_fo_name(title, domain):
    # Clean up title to get FO name
    if not title:
        return domain.split(".")[0].title()

    # Remove common suffixes
    name = title
    for suffix in [
        "| Family Office",
        "- Family Office",
        "| Home",
        "- Home",
        "| Welcome",
        "- Welcome",
        "| About",
        "| Investment",
        "- Investment Office",
    ]:
        name = name.replace(suffix, "").strip()

    return name[:100] if name else domain.split(".")[0].title()


def guess_location(title, description, url):
    combined = f"{title} {description} {url}".lower()

    cities = {
        "new york": ("New York", "United States", "North America"),
        "london": ("London", "United Kingdom", "Europe"),
        "singapore": ("Singapore", "Singapore", "Asia Pacific"),
        "dubai": ("Dubai", "UAE", "Middle East"),
        "zurich": ("Zurich", "Switzerland", "Europe"),
        "hong kong": ("Hong Kong", "Hong Kong", "Asia Pacific"),
        "toronto": ("Toronto", "Canada", "North America"),
        "sydney": ("Sydney", "Australia", "Asia Pacific"),
        "geneva": ("Geneva", "Switzerland", "Europe"),
        "san francisco": ("San Francisco", "United States", "North America"),
        "chicago": ("Chicago", "United States", "North America"),
        "boston": ("Boston", "United States", "North America"),
        "miami": ("Miami", "United States", "North America"),
        "los angeles": ("Los Angeles", "United States", "North America"),
        "dallas": ("Dallas", "United States", "North America"),
        "houston": ("Houston", "United States", "North America"),
        "amsterdam": ("Amsterdam", "Netherlands", "Europe"),
        "frankfurt": ("Frankfurt", "Germany", "Europe"),
        "paris": ("Paris", "France", "Europe"),
        "tokyo": ("Tokyo", "Japan", "Asia Pacific"),
        "shanghai": ("Shanghai", "China", "Asia Pacific"),
        "mumbai": ("Mumbai", "India", "Asia Pacific"),
        "abu dhabi": ("Abu Dhabi", "UAE", "Middle East"),
        "luxembourg": ("Luxembourg", "Luxembourg", "Europe"),
    }

    for city_key, (city, country, region) in cities.items():
        if city_key in combined:
            return city, country, region

    # Try country-level detection
    countries = {
        "united states": ("Unknown", "United States", "North America"),
        " usa ": ("Unknown", "United States", "North America"),
        "united kingdom": ("Unknown", "United Kingdom", "Europe"),
        " uk ": ("Unknown", "United Kingdom", "Europe"),
        "australia": ("Unknown", "Australia", "Asia Pacific"),
        "canada": ("Unknown", "Canada", "North America"),
        "germany": ("Unknown", "Germany", "Europe"),
        "france": ("Unknown", "France", "Europe"),
        "switzerland": ("Unknown", "Switzerland", "Europe"),
        "japan": ("Unknown", "Japan", "Asia Pacific"),
    }

    for country_key, location in countries.items():
        if country_key in combined:
            return location

    return ("Unknown", "Unknown", "Unknown")


def main():
    print("Loading raw Google results...")
    with Path("raw/google_results.json").open("r", encoding="utf-8") as f:
        raw_data = json.load(f)

    print(f"Total raw results: {len(raw_data)}")

    seen_domains = {}

    for item in raw_data:
        url = item.get("url", "")
        title = item.get("title", "")
        description = item.get("description", "")
        query_used = item.get("query_used", "")

        domain = extract_domain(url)
        if not domain:
            continue

        is_fo, fo_type, confidence = classify_family_office(title, description, url, domain)

        if not is_fo:
            continue

        # Keep highest confidence version per domain
        if domain in seen_domains and confidence <= seen_domains[domain]["confidence_score"]:
            continue

        city, country, region = guess_location(title, description, url)

        record = {
            "fo_name": extract_fo_name(title, domain),
            "fo_type": fo_type,
            "website": get_base_url(url),
            "domain": domain,
            "hq_city": city,
            "hq_country": country,
            "hq_region": region,
            "description": description[:300] if description else "",
            "source_url": url,
            "query_used": query_used,
            "confidence_score": confidence,
            "year_founded": "Unknown",
            "aum_range": "Unknown",
        }

        seen_domains[domain] = record

    results = list(seen_domains.values())
    results.sort(key=lambda x: x["confidence_score"], reverse=True)

    Path("data").mkdir(parents=True, exist_ok=True)
    if results:
        fieldnames = list(results[0].keys())
        with Path("data/fo_raw_extracted.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

    # Summary
    sfo = sum(1 for r in results if r["fo_type"] == "SFO")
    mfo = sum(1 for r in results if r["fo_type"] == "MFO")
    countries = len({r["hq_country"] for r in results if r["hq_country"] != "Unknown"})

    print(f"\n{'=' * 50}")
    print(f"Total URLs classified: {len(raw_data)}")
    print(f"Confirmed family offices: {len(results)}")
    print(f"SFO count: {sfo}")
    print(f"MFO count: {mfo}")
    print(f"Countries found: {countries}")
    print("Saved to data/fo_raw_extracted.csv")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
