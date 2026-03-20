import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

HUNTER_API_KEY = os.getenv("HUNTER_API_KEY")

DOMAIN_SEARCH_URL = "https://api.hunter.io/v2/domain-search"
EMAIL_VERIFY_URL = "https://api.hunter.io/v2/email-verifier"


def as_str(value):
    if value is None:
        return ""
    return str(value)


def safe_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return default


def is_empty(value):
    v = as_str(value).strip().lower()
    return v == "" or v == "nan" or v == "none"


def hunter_domain_search(domain):
    params = {
        "domain": domain,
        "api_key": HUNTER_API_KEY,
        "limit": 5,
        "type": "personal",
    }
    try:
        response = requests.get(DOMAIN_SEARCH_URL, params=params, timeout=10)
        response.raise_for_status()
        payload = response.json().get("data", {})
        emails = payload.get("emails", []) or []
        score = payload.get("score", "")

        result = {
            "hunter_email_1": "",
            "hunter_email_2": "",
            "hunter_first_name_1": "",
            "hunter_last_name_1": "",
            "hunter_position_1": "",
            "hunter_domain_confidence": as_str(score),
        }

        if len(emails) >= 1:
            first = emails[0] or {}
            result["hunter_email_1"] = as_str(first.get("value", ""))
            result["hunter_first_name_1"] = as_str(first.get("first_name", ""))
            result["hunter_last_name_1"] = as_str(first.get("last_name", ""))
            result["hunter_position_1"] = as_str(first.get("position", ""))
        if len(emails) >= 2:
            second = emails[1] or {}
            result["hunter_email_2"] = as_str(second.get("value", ""))

        return result, None
    except Exception as exc:
        return None, str(exc)
    finally:
        time.sleep(2)


def hunter_verify_email(email):
    params = {"email": email, "api_key": HUNTER_API_KEY}
    try:
        response = requests.get(EMAIL_VERIFY_URL, params=params, timeout=10)
        response.raise_for_status()
        payload = response.json().get("data", {})
        status = as_str(payload.get("status", "unknown"))
        score = safe_int(payload.get("score", 0), default=0)
        return {"status": status, "score": score}, None
    except Exception as exc:
        return None, str(exc)
    finally:
        time.sleep(2)


def pick_best_email(row):
    # 1) First valid Apollo email
    for i in range(1, 4):
        email = as_str(row.get(f"dm_email_{i}", "")).strip()
        status = as_str(row.get(f"dm_email_{i}_status", "")).strip().lower()
        score = safe_int(row.get(f"dm_email_{i}_score", 0), default=0)
        if email and status == "valid" and score >= 70:
            return email, score

    # 2) First Hunter email
    hunter_1 = as_str(row.get("hunter_email_1", "")).strip()
    if hunter_1:
        return hunter_1, safe_int(row.get("hunter_domain_confidence", 0), default=0)
    hunter_2 = as_str(row.get("hunter_email_2", "")).strip()
    if hunter_2:
        return hunter_2, safe_int(row.get("hunter_domain_confidence", 0), default=0)

    # 3) First Apollo email regardless of score
    for i in range(1, 4):
        email = as_str(row.get(f"dm_email_{i}", "")).strip()
        if email:
            return email, safe_int(row.get(f"dm_email_{i}_score", 0), default=0)

    return "", 0


def get_coverage(best_email, best_score):
    if not best_email:
        return "None"
    if best_score >= 70:
        return "Strong"
    if best_score >= 40:
        return "Moderate"
    return "Weak"


def main():
    if not HUNTER_API_KEY:
        raise RuntimeError("Missing HUNTER_API_KEY in .env")

    in_path = "data/fo_apollo_enriched.csv"
    out_path = "data/fo_hunter_verified.csv"

    print("Loading Apollo-enriched file...")
    df = pd.read_csv(in_path)
    total = len(df)
    print(f"Total records to verify: {total}")

    new_cols = [
        "hunter_email_1",
        "hunter_email_2",
        "hunter_first_name_1",
        "hunter_last_name_1",
        "hunter_position_1",
        "hunter_domain_confidence",
        "dm_email_1_status",
        "dm_email_1_score",
        "dm_email_2_status",
        "dm_email_2_score",
        "dm_email_3_status",
        "dm_email_3_score",
        "best_email",
        "email_coverage",
    ]
    for col in new_cols:
        if col not in df.columns:
            df[col] = ""

    for idx, row in df.iterrows():
        domain = as_str(row.get("domain", "")).strip()

        # Domain search
        if not is_empty(domain):
            domain_result, domain_err = hunter_domain_search(domain)
            if domain_result:
                for k, v in domain_result.items():
                    df.at[idx, k] = as_str(v)
            else:
                print(f"[{idx + 1}/{total}] Hunter domain error for {domain}: {domain_err}")

        # Verify Apollo emails (only if row confidence >= 40)
        row_score = safe_int(row.get("confidence_score", 0), default=0)
        for email_idx in range(1, 4):
            email_col = f"dm_email_{email_idx}"
            status_col = f"dm_email_{email_idx}_status"
            score_col = f"dm_email_{email_idx}_score"

            email = as_str(row.get(email_col, "")).strip()
            if is_empty(email):
                df.at[idx, status_col] = "unverified"
                df.at[idx, score_col] = "0"
                continue

            if row_score < 40:
                df.at[idx, status_col] = "unverified"
                df.at[idx, score_col] = "0"
                continue

            verified, verify_err = hunter_verify_email(email)
            if verified:
                df.at[idx, status_col] = as_str(verified.get("status", "unknown"))
                df.at[idx, score_col] = as_str(verified.get("score", 0))
            else:
                df.at[idx, status_col] = "unverified"
                df.at[idx, score_col] = "0"
                print(f"[{idx + 1}/{total}] Hunter verify error for {email}: {verify_err}")

        # best_email + coverage
        current_row = df.loc[idx]
        best_email, best_score = pick_best_email(current_row)
        coverage = get_coverage(best_email, best_score)
        df.at[idx, "best_email"] = as_str(best_email)
        df.at[idx, "email_coverage"] = as_str(coverage)

        if (idx + 1) % 5 == 0:
            df = df.astype(str)
            df.to_csv(out_path, index=False)

        if (idx + 1) % 10 == 0:
            status = as_str(df.at[idx, "dm_email_1_status"])
            score = as_str(df.at[idx, "dm_email_1_score"])
            print(f"[{idx + 1}/{total}] {domain} - email_status: {status} (score: {score})")

    df = df.astype(str)
    df.to_csv(out_path, index=False)

    strong = int((df["email_coverage"] == "Strong").sum())
    moderate = int((df["email_coverage"] == "Moderate").sum())
    weak = int((df["email_coverage"] == "Weak").sum())
    none = int((df["email_coverage"] == "None").sum())

    def pct(n):
        return (n / total * 100) if total else 0

    print("\nHunter Verification Complete")
    print(f"Total processed: {total}")
    print(f"Strong coverage: {strong} ({pct(strong):.1f}%)")
    print(f"Moderate coverage: {moderate} ({pct(moderate):.1f}%)")
    print(f"Weak coverage: {weak} ({pct(weak):.1f}%)")
    print(f"No email found: {none} ({pct(none):.1f}%)")
    print("Saved to data/fo_hunter_verified.csv")


if __name__ == "__main__":
    main()
