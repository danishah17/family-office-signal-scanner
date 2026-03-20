import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")


def get_org_from_apollo(domain):
    """Search Apollo for organization by domain."""
    url = "https://api.apollo.io/api/v1/organizations/search"
    headers = {"X-Api-Key": APOLLO_API_KEY, "Content-Type": "application/json"}
    payload = {"q_organization_domains": domain, "page": 1, "per_page": 1}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            data = response.json()
            orgs = data.get("organizations", [])
            if orgs:
                return orgs[0]
        return None
    except Exception as e:
        print(f"  Apollo org error for {domain}: {e}")
        return None


def get_people_from_apollo(org_id, domain):
    """Search Apollo for decision makers at this org."""
    url = "https://api.apollo.io/api/v1/mixed_people/search"
    headers = {"X-Api-Key": APOLLO_API_KEY, "Content-Type": "application/json"}
    payload = {
        "organization_ids": [org_id] if org_id else [],
        "q_organization_domains": domain,
        "person_titles": [
            "Chief Investment Officer",
            "CIO",
            "Managing Director",
            "Investment Director",
            "Principal",
            "Partner",
            "Family Office Director",
            "Founder",
            "President",
            "Head of Investments",
            "Portfolio Manager",
            "Director",
            "Investment Manager",
        ],
        "page": 1,
        "per_page": 3,
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return data.get("people", [])
        return []
    except Exception as e:
        print(f"  Apollo people error for {domain}: {e}")
        return []


def extract_org_fields(org):
    """Extract relevant fields from Apollo org response."""
    if not org:
        return {}
    return {
        "apollo_id": org.get("id", ""),
        "employee_count": str(org.get("num_employees", "Unknown")),
        "linkedin_url": org.get("linkedin_url", ""),
        "phone": org.get("phone", ""),
        "founded_year": str(org.get("founded_year", "Unknown")),
        "apollo_keywords": ", ".join(org.get("keywords", [])[:5]),
        "apollo_description": (org.get("short_description") or "")[:200],
        "apollo_industry": org.get("industry", ""),
        "apollo_city": org.get("city", ""),
        "apollo_country": org.get("country", ""),
    }


def extract_person_fields(people):
    """Extract up to 3 decision makers from Apollo people response."""
    result = {}
    for i, person in enumerate(people[:3], 1):
        result[f"dm_name_{i}"] = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
        result[f"dm_title_{i}"] = person.get("title", "")
        result[f"dm_email_{i}"] = person.get("email", "")
        result[f"dm_linkedin_{i}"] = person.get("linkedin_url", "")
        result[f"dm_phone_{i}"] = (
            person.get("phone_numbers", [{}])[0].get("sanitized_number", "")
            if person.get("phone_numbers")
            else ""
        )

    # Fill empty slots.
    for i in range(len(people) + 1, 4):
        result[f"dm_name_{i}"] = ""
        result[f"dm_title_{i}"] = ""
        result[f"dm_email_{i}"] = ""
        result[f"dm_linkedin_{i}"] = ""
        result[f"dm_phone_{i}"] = ""

    return result


def main():
    if not APOLLO_API_KEY:
        raise RuntimeError("Missing APOLLO_API_KEY in .env")

    print("Loading extracted family offices...")
    df = pd.read_csv("data/fo_raw_extracted.csv")
    print(f"Total records to enrich: {len(df)}")

    # Add Apollo columns.
    apollo_cols = [
        "apollo_id",
        "employee_count",
        "linkedin_url",
        "phone",
        "founded_year",
        "apollo_keywords",
        "apollo_description",
        "apollo_industry",
        "apollo_city",
        "apollo_country",
        "dm_name_1",
        "dm_title_1",
        "dm_email_1",
        "dm_linkedin_1",
        "dm_phone_1",
        "dm_name_2",
        "dm_title_2",
        "dm_email_2",
        "dm_linkedin_2",
        "dm_phone_2",
        "dm_name_3",
        "dm_title_3",
        "dm_email_3",
        "dm_linkedin_3",
        "dm_phone_3",
        "apollo_enriched",
    ]
    for col in apollo_cols:
        if col not in df.columns:
            df[col] = "" if col != "apollo_enriched" else False

    enriched_count = 0
    dm_found_count = 0

    for idx, row in df.iterrows():
        domain = str(row.get("domain", "")).strip()
        if not domain or domain == "nan":
            continue

        print(f"[{idx + 1}/{len(df)}] Processing: {domain}")

        # Step 1: Get org from Apollo.
        org = get_org_from_apollo(domain)
        org_fields = extract_org_fields(org)
        org_id = org_fields.get("apollo_id", "")

        # Step 2: Get decision makers.
        people = get_people_from_apollo(org_id, domain)
        people_fields = extract_person_fields(people)

        # Step 3: Update dataframe.
        if org_fields:
            for key, val in org_fields.items():
                df.at[idx, key] = "" if val is None else str(val)
            enriched_count += 1

        for key, val in people_fields.items():
            df.at[idx, key] = "" if val is None else str(val)

        if people:
            dm_found_count += len(people)
            df.at[idx, "apollo_enriched"] = True
            print(f"  [OK] Found {len(people)} decision makers")
        else:
            print("  — No decision makers found")

        # Override location with Apollo data if better.
        if org_fields.get("apollo_city") and row.get("hq_city", "") == "Unknown":
            df.at[idx, "hq_city"] = org_fields["apollo_city"]
        if org_fields.get("apollo_country") and row.get("hq_country", "") == "Unknown":
            df.at[idx, "hq_country"] = org_fields["apollo_country"]

        # Save progress every 10 records.
        if (idx + 1) % 10 == 0:
            df.to_csv("data/fo_apollo_enriched.csv", index=False)
            print(f"  Progress saved - {idx + 1} records processed")

        time.sleep(3)

    # Final save.
    df.to_csv("data/fo_apollo_enriched.csv", index=False)

    print(f"\n{'=' * 50}")
    print("Apollo Enrichment Complete")
    print(f"Total processed: {len(df)}")
    print(f"Orgs enriched: {enriched_count}")
    print(f"Total DMs found: {dm_found_count}")
    print(f"Avg DMs per enriched org: {dm_found_count / max(enriched_count, 1):.1f}")
    print("Saved to data/fo_apollo_enriched.csv")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
