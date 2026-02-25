#!/usr/bin/env python3
"""
Job Search Automation for Krish Sawhney
Uses free public APIs: Adzuna, RemoteOK, and direct RSS/JSON feeds
No API keys required for initial search.

Usage (inside Railway container):
  python3 /data/workspace/job_search/scripts/search_jobs.py
  python3 /data/workspace/job_search/scripts/search_jobs.py --region uk
  python3 /data/workspace/job_search/scripts/search_jobs.py --role "ai engineer"
"""

import json
import csv
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent
JOB_DIR      = SCRIPT_DIR.parent
PROFILE_PATH = JOB_DIR / "profile.json"
TRACKER_PATH = JOB_DIR / "tracker.csv"
LEADS_DIR    = JOB_DIR / "leads"
LEADS_DIR.mkdir(exist_ok=True)

# ── Load profile ──────────────────────────────────────────────────────────────
with open(PROFILE_PATH) as f:
    PROFILE = json.load(f)

TARGET_ROLES = PROFILE["target_roles"]

# ── Search keywords built from profile ───────────────────────────────────────
SEARCH_TERMS = [
    "junior ai engineer",
    "junior software developer",
    "fullstack developer junior",
    "junior ml engineer",
    "associate software engineer python",
    "junior backend developer node",
    "ai developer junior",
    "graduate software engineer",
    "junior reinforcement learning",
    "junior machine learning engineer",
]

# ── Adzuna country codes ──────────────────────────────────────────────────────
ADZUNA_REGIONS = {
    "uk":      {"country": "gb", "location": ""},
    # "uae": not supported by Adzuna — UAE jobs sourced via separate scraper
    "india":   {"country": "in", "location": ""},
    "germany": {"country": "de", "location": ""},
    "netherlands": {"country": "nl", "location": ""},
}

# Adzuna public endpoint (no API key required for basic search via web)
# We use their public JSON API — app_id/app_key can be omitted for low-volume
ADZUNA_APP_ID  = os.environ.get("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JobBot/1.0; +https://bertram.co.in)",
    "Accept": "application/json",
}


def fetch_json(url: str, timeout: int = 15) -> dict | None:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  [HTTP {e.code}] {url}")
        return None
    except Exception as e:
        print(f"  [ERR] {e} — {url}")
        return None


# ── Source 1: Adzuna API ──────────────────────────────────────────────────────
def search_adzuna(role: str, country_code: str, max_pages: int = 3) -> list[dict]:
    jobs = []
    for page in range(1, max_pages + 1):
        params = {
            "results_per_page": 20,
            "what": role,
            "content-type": "application/json",
        }
        if ADZUNA_APP_ID and ADZUNA_APP_KEY:
            params["app_id"]  = ADZUNA_APP_ID
            params["app_key"] = ADZUNA_APP_KEY

        qs  = urllib.parse.urlencode(params)
        url = f"https://api.adzuna.com/v1/api/jobs/{country_code}/search/{page}?{qs}"
        data = fetch_json(url)
        if not data or "results" not in data:
            break
        for item in data["results"]:
            jobs.append({
                "source":    "adzuna",
                "title":     item.get("title", ""),
                "company":   item.get("company", {}).get("display_name", ""),
                "location":  item.get("location", {}).get("display_name", ""),
                "url":       item.get("redirect_url", ""),
                "salary":    item.get("salary_min", ""),
                "posted":    item.get("created", ""),
                "region":    country_code,
                "role_query": role,
            })
        time.sleep(0.5)
    return jobs


# ── Source 2: RemoteOK (global remote jobs) ───────────────────────────────────
def search_remoteok(role: str) -> list[dict]:
    url  = f"https://remoteok.com/api?tag={urllib.parse.quote(role)}"
    data = fetch_json(url)
    if not data or not isinstance(data, list):
        return []
    jobs = []
    for item in data[1:]:  # first item is metadata
        if not isinstance(item, dict):
            continue
        jobs.append({
            "source":    "remoteok",
            "title":     item.get("position", ""),
            "company":   item.get("company", ""),
            "location":  "Remote",
            "url":       item.get("url", ""),
            "salary":    item.get("salary", ""),
            "posted":    item.get("date", ""),
            "region":    "remote",
            "role_query": role,
        })
    time.sleep(0.5)
    return jobs


# ── Source 3: Remotive (tech-focused remote) ──────────────────────────────────
def search_remotive(role: str) -> list[dict]:
    url  = f"https://remotive.com/api/remote-jobs?search={urllib.parse.quote(role)}&limit=50"
    data = fetch_json(url)
    if not data or "jobs" not in data:
        return []
    jobs = []
    for item in data["jobs"]:
        jobs.append({
            "source":    "remotive",
            "title":     item.get("title", ""),
            "company":   item.get("company_name", ""),
            "location":  item.get("candidate_required_location", "Remote"),
            "url":       item.get("url", ""),
            "salary":    item.get("salary", ""),
            "posted":    item.get("publication_date", ""),
            "region":    "remote",
            "role_query": role,
        })
    time.sleep(0.5)
    return jobs


# ── Source 4: Reed.co.uk (UK jobs, public RSS) ────────────────────────────────
def search_reed(role: str) -> list[dict]:
    """Reed has a public API that requires a (free) API key.
    Without a key, we scrape their search page via their public JSON endpoint.
    Register free at https://www.reed.co.uk/developers/jobseeker to get a key.
    Set REED_API_KEY env var in Railway."""
    reed_key = os.environ.get("REED_API_KEY", "")
    if not reed_key:
        return []

    url = (
        f"https://www.reed.co.uk/api/1.0/search?"
        f"keywords={urllib.parse.quote(role)}&locationName=UK&distancefromlocation=50"
    )
    req = urllib.request.Request(url, headers={
        **HEADERS,
        "Authorization": f"Basic {__import__('base64').b64encode(f'{reed_key}:'.encode()).decode()}"
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"  [Reed ERR] {e}")
        return []

    jobs = []
    for item in data.get("results", []):
        jobs.append({
            "source":    "reed",
            "title":     item.get("jobTitle", ""),
            "company":   item.get("employerName", ""),
            "location":  item.get("locationName", ""),
            "url":       item.get("jobUrl", ""),
            "salary":    f"{item.get('minimumSalary','')}-{item.get('maximumSalary','')}",
            "posted":    item.get("date", ""),
            "region":    "uk",
            "role_query": role,
        })
    return jobs


# ── Source 5: The Muse (UAE / Dubai roles, free API) ─────────────────────────
def search_themuse_uae(role: str) -> list[dict]:
    url = (
        f"https://www.themuse.com/api/public/jobs?"
        f"category=Software+Engineer&location=Dubai%2C+United+Arab+Emirates"
        f"&level=Entry+Level&level=Mid+Level&page=1"
    )
    data = fetch_json(url)
    if not data or "results" not in data:
        return []
    jobs = []
    for item in data["results"]:
        title = item.get("name", "")
        if role.split()[0].lower() not in title.lower() and "software" not in title.lower() and "developer" not in title.lower():
            continue
        company = item.get("company", {}).get("name", "")
        locations = [loc.get("name", "") for loc in item.get("locations", [])]
        jobs.append({
            "source":    "themuse",
            "title":     title,
            "company":   company,
            "location":  ", ".join(locations) or "UAE",
            "url":       item.get("refs", {}).get("landing_page", ""),
            "salary":    "",
            "posted":    item.get("publication_date", ""),
            "region":    "uae",
            "role_query": role,
        })
    time.sleep(0.5)
    return jobs


# ── Relevance scoring ─────────────────────────────────────────────────────────
MUST_HAVE_KEYWORDS = [
    "python", "javascript", "typescript", "node", "react", "ai", "ml",
    "machine learning", "fullstack", "full-stack", "full stack", "backend",
    "software engineer", "developer", "junior", "graduate", "associate",
    "reinforcement", "llm", "nlp", "docker", "cloud"
]

EXCLUDE_KEYWORDS = [
    "senior", "lead", "principal", "director", "manager", "10+ years",
    "8+ years", "7+ years", "architect"
]

def score_job(job: dict) -> int:
    text = (job["title"] + " " + job.get("company", "")).lower()
    score = 0
    for kw in MUST_HAVE_KEYWORDS:
        if kw in text:
            score += 2
    for kw in EXCLUDE_KEYWORDS:
        if kw in text:
            score -= 10
    # Boost junior/graduate
    if any(w in text for w in ["junior", "graduate", "associate", "entry"]):
        score += 5
    return score


def is_relevant(job: dict) -> bool:
    return score_job(job) > -5


# ── Dedup ─────────────────────────────────────────────────────────────────────
def dedup(jobs: list[dict]) -> list[dict]:
    seen = set()
    out  = []
    for j in jobs:
        key = (j["title"].lower().strip(), j["company"].lower().strip())
        if key not in seen:
            seen.add(key)
            out.append(j)
    return out


# ── Load existing tracker ─────────────────────────────────────────────────────
TRACKER_FIELDS = ["id", "date_found", "title", "company", "location", "region",
                  "source", "url", "salary", "score", "status", "cover_letter_file", "notes"]

def load_tracker() -> dict[str, dict]:
    existing = {}
    if TRACKER_PATH.exists():
        with open(TRACKER_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # If the CSV has incompatible headers (e.g. from a previous session), start fresh
            if not reader.fieldnames or "title" not in reader.fieldnames:
                print(f"  [tracker] Incompatible CSV format — starting fresh")
                return {}
            for row in reader:
                key = (row["title"].lower().strip(), row["company"].lower().strip())
                existing[key] = row
    return existing


def save_tracker(jobs: list[dict], existing: dict):
    # Merge new jobs with existing
    all_rows = list(existing.values())
    existing_keys = set(existing.keys())

    new_count = 0
    for j in jobs:
        key = (j["title"].lower().strip(), j["company"].lower().strip())
        if key not in existing_keys:
            row_id = len(all_rows) + 1
            all_rows.append({
                "id":                str(row_id),
                "date_found":        datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "title":             j["title"],
                "company":           j["company"],
                "location":          j["location"],
                "region":            j["region"],
                "source":            j["source"],
                "url":               j["url"],
                "salary":            str(j.get("salary", "")),
                "score":             str(score_job(j)),
                "status":            "found",
                "cover_letter_file": "",
                "notes":             "",
            })
            existing_keys.add(key)
            new_count += 1

    with open(TRACKER_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRACKER_FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)

    return new_count


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Job search automation for Krish Sawhney")
    parser.add_argument("--region",  default="all",  help="uk | uae | india | germany | netherlands | remote | all")
    parser.add_argument("--role",    default="all",  help="Specific role to search, or 'all'")
    parser.add_argument("--max",     type=int, default=3, help="Max Adzuna pages per query (20 results/page)")
    args = parser.parse_args()

    roles = SEARCH_TERMS if args.role == "all" else [args.role]
    regions = list(ADZUNA_REGIONS.keys()) if args.region == "all" else [args.region.lower()]

    all_jobs: list[dict] = []

    print(f"\n{'='*60}")
    print(f"  Job Search — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Regions : {', '.join(regions)}")
    print(f"  Roles   : {len(roles)} search terms")
    print(f"{'='*60}\n")

    # ── Adzuna ──
    for region in regions:
        if region == "remote":
            continue
        adzuna_country = ADZUNA_REGIONS.get(region, {}).get("country")
        if not adzuna_country:
            print(f"[SKIP] Unknown region: {region}")
            continue
        print(f"[Adzuna] Searching {region.upper()}...")
        for role in roles[:5]:  # limit to top 5 terms to avoid rate limits
            jobs = search_adzuna(role, adzuna_country, args.max)
            relevant = [j for j in jobs if is_relevant(j)]
            all_jobs.extend(relevant)
            print(f"  '{role}' → {len(jobs)} found, {len(relevant)} relevant")

    # ── UAE via The Muse (Adzuna doesn't cover ae) ──
    if args.region in ("all", "uae"):
        print("\n[TheMuse] Searching UAE roles...")
        for role in ["junior software engineer", "fullstack developer", "developer"]:
            jobs = search_themuse_uae(role)
            relevant = [j for j in jobs if is_relevant(j)]
            all_jobs.extend(relevant)
            print(f"  '{role}' → {len(jobs)} found, {len(relevant)} relevant")

    # ── RemoteOK ──
    if args.region in ("all", "remote"):
        print("\n[RemoteOK] Searching remote roles...")
        for role in ["junior ai engineer", "junior fullstack developer", "junior python developer"]:
            jobs = search_remoteok(role)
            relevant = [j for j in jobs if is_relevant(j)]
            all_jobs.extend(relevant)
            print(f"  '{role}' → {len(jobs)} found, {len(relevant)} relevant")

    # ── Remotive ──
    if args.region in ("all", "remote"):
        print("\n[Remotive] Searching remote roles...")
        for role in ["junior software engineer", "fullstack developer", "ml engineer"]:
            jobs = search_remotive(role)
            relevant = [j for j in jobs if is_relevant(j)]
            all_jobs.extend(relevant)
            print(f"  '{role}' → {len(jobs)} found, {len(relevant)} relevant")

    # ── Reed (UK, if key set) ──
    if os.environ.get("REED_API_KEY") and args.region in ("all", "uk"):
        print("\n[Reed] Searching UK roles...")
        for role in ["junior ai developer", "junior fullstack developer"]:
            jobs = search_reed(role)
            relevant = [j for j in jobs if is_relevant(j)]
            all_jobs.extend(relevant)
            print(f"  '{role}' → {len(jobs)} found, {len(relevant)} relevant")

    # ── Dedup + save ──
    all_jobs = dedup(all_jobs)
    all_jobs.sort(key=lambda j: score_job(j), reverse=True)

    existing = load_tracker()
    new_count = save_tracker(all_jobs, existing)

    # ── Print summary ──
    print(f"\n{'='*60}")
    print(f"  Total unique jobs found : {len(all_jobs)}")
    print(f"  New jobs added          : {new_count}")
    print(f"  Tracker saved to        : {TRACKER_PATH}")
    print(f"{'='*60}")

    # Save a fresh leads file (top 30, sorted by score)
    leads_file = LEADS_DIR / f"leads_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(leads_file, "w") as f:
        json.dump(all_jobs[:30], f, indent=2)
    print(f"  Leads snapshot saved    : {leads_file}")

    # Print top 15
    print("\n── Top 15 Leads ─────────────────────────────────────────")
    for i, j in enumerate(all_jobs[:15], 1):
        print(f"  {i:>2}. [{j['region'].upper():^5}] {j['title'][:45]:<45} | {j['company'][:25]:<25} | {j['url'][:60]}")

    print(f"\nNext step: run apply.py to generate cover letters and draft applications.\n")


if __name__ == "__main__":
    main()
