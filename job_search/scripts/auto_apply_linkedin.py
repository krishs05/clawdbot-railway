#!/usr/bin/env python3
"""
LinkedIn Easy Apply Automation for Krish Sawhney
Uses Playwright + li_at cookie — no login required.

Setup (run once in container):
  bash /data/workspace/job_search/scripts/install_playwright.sh

Usage:
  # Dry run — find jobs, don't submit
  python3 auto_apply_linkedin.py --dry-run

  # Apply to all matching jobs (UK)
  python3 auto_apply_linkedin.py --region uk

  # Apply, specific role
  python3 auto_apply_linkedin.py --region india --role "junior ai engineer"

  # Limit to N applications per run
  python3 auto_apply_linkedin.py --region uk --max 10
"""

import os
import sys
import json
import csv
import time
import random
import argparse
from pathlib import Path
from datetime import datetime, timezone

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    print("[ERROR] Playwright not installed. Run:")
    print("  bash /data/workspace/job_search/scripts/install_playwright.sh")
    sys.exit(1)

# ── Paths & config ────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent
JOB_DIR      = SCRIPT_DIR.parent
PROFILE_PATH = JOB_DIR / "profile.json"
TRACKER_PATH = JOB_DIR / "tracker.csv"
COVERS_DIR   = JOB_DIR / "cover_letters"
LOG_DIR      = JOB_DIR / "apply_logs"
LOG_DIR.mkdir(exist_ok=True)

LI_AT   = os.environ.get("LINKEDIN_LI_AT", "")
CV_PATH = os.environ.get("CV_PATH", str(JOB_DIR / "Krish_Sawhney_CV.pdf"))

with open(PROFILE_PATH) as f:
    P = json.load(f)

TRACKER_FIELDS = ["id", "date_found", "title", "company", "location", "region",
                  "source", "url", "salary", "score", "status", "cover_letter_file", "notes"]

# ── LinkedIn search configs per region ───────────────────────────────────────
REGION_CONFIGS = {
    "uk": {
        "location": "United Kingdom",
        "geo_id": "101165590",
    },
    "india": {
        "location": "India",
        "geo_id": "102713980",
    },
    "germany": {
        "location": "Germany",
        "geo_id": "101282230",
    },
    "netherlands": {
        "location": "Netherlands",
        "geo_id": "102890719",
    },
    "uae": {
        "location": "United Arab Emirates",
        "geo_id": "104305776",
    },
}

SEARCH_ROLES = [
    "junior ai engineer",
    "junior software developer",
    "junior software engineer",
    "junior fullstack developer",
    "junior ml engineer",
    "associate software engineer",
]

# ── Tracker helpers ───────────────────────────────────────────────────────────
def load_tracker() -> dict:
    existing = {}
    if TRACKER_PATH.exists():
        with open(TRACKER_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames and "title" in reader.fieldnames:
                for row in reader:
                    existing[row.get("url", "")] = row
    return existing


def update_tracker_status(url: str, status: str, notes: str = ""):
    rows = []
    updated = False
    if TRACKER_PATH.exists():
        with open(TRACKER_PATH, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            if r.get("url", "").startswith(url[:60]):
                r["status"] = status
                r["notes"]  = (r.get("notes", "") + f" | {notes}").strip(" |")
                updated = True
        if updated:
            with open(TRACKER_PATH, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=TRACKER_FIELDS)
                writer.writeheader()
                writer.writerows(rows)


def add_to_tracker(job: dict):
    rows = []
    if TRACKER_PATH.exists():
        with open(TRACKER_PATH, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    row_id = len(rows) + 1
    rows.append({
        "id":                str(row_id),
        "date_found":        datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "title":             job.get("title", ""),
        "company":           job.get("company", ""),
        "location":          job.get("location", ""),
        "region":            job.get("region", ""),
        "source":            "linkedin_auto",
        "url":               job.get("url", ""),
        "salary":            "",
        "score":             "10",
        "status":            job.get("status", "applied"),
        "cover_letter_file": "",
        "notes":             job.get("notes", ""),
    })
    with open(TRACKER_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRACKER_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


# ── Cover letter loader ───────────────────────────────────────────────────────
def get_cover_letter(job_title: str) -> str:
    # Try to find an existing cover letter for a similar role
    title_lower = job_title.lower()
    for cl_file in COVERS_DIR.glob("*.txt"):
        if any(w in cl_file.name.lower() for w in title_lower.split()[:2]):
            return cl_file.read_text(encoding="utf-8")[:2900]  # LinkedIn limit
    # Fallback to generic
    generic = list(COVERS_DIR.glob("6_*.txt"))
    if generic:
        return generic[0].read_text(encoding="utf-8")[:2900]
    return ""


# ── Common form answers ───────────────────────────────────────────────────────
COMMON_ANSWERS = {
    # Phone
    "phone": P["personal"]["phone"],
    "mobile": P["personal"]["phone"],
    # Location
    "city": "New Delhi",
    "location": "New Delhi, India",
    "current location": "New Delhi, India",
    # Work authorisation
    "authorised": "No",
    "authorized": "No",
    "right to work": "No",
    "visa": "Yes, I require sponsorship",
    "sponsorship": "Yes",
    "require sponsorship": "Yes",
    # Experience
    "years of experience": "1",
    "how many years": "1",
    "notice period": "30",
    "when can you start": "30 days",
    "available": "30 days notice",
    # Salary
    "salary expectation": "Open to discussion",
    "expected salary": "Open to discussion",
    "desired salary": "Open to discussion",
    # LinkedIn / URLs
    "linkedin": "https://linkedin.com/in/krish-sawhney-824416261",
    "github": "https://github.com/krishs05",
    "portfolio": "https://bertram.co.in",
    "website": "https://bertram.co.in",
    # Yes/No standard
    "degree": "Yes",
    "bachelor": "Yes",
    "legally": "No",
    "18 years": "Yes",
    "full time": "Yes",
    "willing to relocate": "Yes",
    "hybrid": "Yes",
    "remote": "Yes",
}


def answer_field(page, label_text: str, input_el) -> bool:
    """Try to fill an input based on its label text."""
    label_lower = label_text.lower().strip()
    for key, val in COMMON_ANSWERS.items():
        if key in label_lower:
            try:
                tag = input_el.evaluate("el => el.tagName.toLowerCase()")
                if tag == "select":
                    # Try to select by label text first
                    options = input_el.query_selector_all("option")
                    for opt in options:
                        opt_text = opt.inner_text().lower()
                        if val.lower() in opt_text or opt_text in val.lower():
                            input_el.select_option(value=opt.get_attribute("value"))
                            return True
                    # Fallback: select first non-empty option
                    input_el.select_option(index=1)
                    return True
                elif tag in ("input", "textarea"):
                    input_type = input_el.get_attribute("type") or "text"
                    if input_type == "checkbox":
                        if val.lower() in ("yes", "true", "1"):
                            if not input_el.is_checked():
                                input_el.check()
                        return True
                    elif input_type == "radio":
                        return False  # handled separately
                    else:
                        input_el.fill(val)
                        return True
            except Exception:
                pass
    return False


# ── Core apply function ───────────────────────────────────────────────────────
def apply_to_job(page, job_url: str, job_title: str, company: str,
                 dry_run: bool = False) -> str:
    """
    Returns: 'applied' | 'skipped' | 'error:<reason>'
    """
    log_lines = [f"[{datetime.now().isoformat()}] {job_title} @ {company}"]

    try:
        page.goto(job_url, timeout=30000)
        page.wait_for_timeout(2000)

        # Check for Easy Apply button
        easy_apply_btn = page.query_selector("button.jobs-apply-button, [aria-label*='Easy Apply']")
        if not easy_apply_btn:
            log_lines.append("  → No Easy Apply button found, skipping")
            return "skipped"

        log_lines.append("  → Easy Apply button found")

        if dry_run:
            log_lines.append("  → DRY RUN — not clicking")
            return "dry_run"

        easy_apply_btn.click()
        page.wait_for_timeout(2000)

        # Multi-step form loop (up to 10 steps)
        for step in range(10):
            log_lines.append(f"  → Step {step + 1}")

            # Upload CV if asked
            file_inputs = page.query_selector_all("input[type='file']")
            for fi in file_inputs:
                if Path(CV_PATH).exists():
                    fi.set_input_files(CV_PATH)
                    log_lines.append("  → Uploaded CV")
                    page.wait_for_timeout(1000)

            # Fill text/select fields
            form_groups = page.query_selector_all(
                ".jobs-easy-apply-form-section__grouping, .fb-form-element"
            )
            for group in form_groups:
                try:
                    label_el = group.query_selector("label, .fb-form-element-label")
                    label_text = label_el.inner_text() if label_el else ""

                    inputs = group.query_selector_all("input:not([type='hidden']):not([type='file']), select, textarea")
                    for inp in inputs:
                        answer_field(page, label_text, inp)

                    # Handle radio buttons
                    radios = group.query_selector_all("input[type='radio']")
                    if radios and label_text:
                        label_lower = label_text.lower()
                        for key, val in COMMON_ANSWERS.items():
                            if key in label_lower:
                                # Find radio matching our answer
                                for radio in radios:
                                    radio_label = page.query_selector(
                                        f"label[for='{radio.get_attribute('id')}']"
                                    )
                                    if radio_label:
                                        rl = radio_label.inner_text().lower()
                                        if val.lower() in rl or rl in val.lower():
                                            radio.click()
                                            break
                                else:
                                    # Default: click first radio
                                    radios[0].click()
                                break
                except Exception:
                    pass

            # Cover letter textarea
            cover_textareas = page.query_selector_all(
                "textarea[id*='cover'], textarea[name*='cover'], "
                ".jobs-easy-apply-form-section textarea"
            )
            if cover_textareas:
                cl = get_cover_letter(job_title)
                if cl:
                    cover_textareas[0].fill(cl)
                    log_lines.append("  → Filled cover letter")

            page.wait_for_timeout(500)

            # Navigation buttons
            next_btn   = page.query_selector("button[aria-label='Continue to next step']")
            review_btn = page.query_selector("button[aria-label='Review your application']")
            submit_btn = page.query_selector("button[aria-label='Submit application']")

            if submit_btn:
                submit_btn.click()
                page.wait_for_timeout(2000)
                log_lines.append("  ✓ Application submitted!")
                # Close confirmation dialog if it appears
                close = page.query_selector("button[aria-label='Dismiss']")
                if close:
                    close.click()
                return "applied"
            elif review_btn:
                review_btn.click()
                page.wait_for_timeout(1500)
            elif next_btn:
                next_btn.click()
                page.wait_for_timeout(1500)
            else:
                log_lines.append("  → No navigation button found, stopping")
                break

        return "error:no_submit_reached"

    except PWTimeout:
        log_lines.append("  → Timeout")
        return "error:timeout"
    except Exception as e:
        log_lines.append(f"  → Exception: {e}")
        return f"error:{str(e)[:80]}"
    finally:
        log_file = LOG_DIR / f"apply_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        log_file.write_text("\n".join(log_lines), encoding="utf-8")


# ── LinkedIn job search ───────────────────────────────────────────────────────
def search_linkedin_jobs(page, role: str, geo_id: str, location: str,
                         max_results: int = 25) -> list[dict]:
    jobs = []
    import urllib.parse
    params = {
        "keywords":   role,
        "location":   location,
        "geoId":      geo_id,
        "f_AL":       "true",   # Easy Apply only
        "f_E":        "1,2",    # Entry level, Associate
        "sortBy":     "DD",     # Date posted
        "start":      "0",
    }
    url = "https://www.linkedin.com/jobs/search/?" + urllib.parse.urlencode(params)
    page.goto(url, timeout=30000)
    page.wait_for_timeout(3000)

    # Scroll to load more results
    for _ in range(3):
        page.keyboard.press("End")
        page.wait_for_timeout(1000)

    job_cards = page.query_selector_all(
        ".job-card-container, .jobs-search-results__list-item"
    )
    for card in job_cards[:max_results]:
        try:
            title_el   = card.query_selector(".job-card-list__title, .base-search-card__title")
            company_el = card.query_selector(".job-card-container__primary-description, .base-search-card__subtitle")
            loc_el     = card.query_selector(".job-card-container__metadata-item, .job-search-card__location")
            link_el    = card.query_selector("a[href*='/jobs/view/']")

            title   = title_el.inner_text().strip()   if title_el   else ""
            company = company_el.inner_text().strip()  if company_el else ""
            loc     = loc_el.inner_text().strip()      if loc_el     else location
            href    = link_el.get_attribute("href")    if link_el    else ""

            if title and href:
                # Clean up URL
                if "?" in href:
                    href = href[:href.index("?")]
                jobs.append({
                    "title":    title,
                    "company":  company,
                    "location": loc,
                    "url":      href if href.startswith("http") else f"https://www.linkedin.com{href}",
                    "region":   "",
                })
        except Exception:
            continue

    return jobs


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region",   default="uk",   help="uk | india | germany | netherlands | uae | all")
    parser.add_argument("--role",     default="all",  help="Specific role or 'all'")
    parser.add_argument("--max",      type=int, default=20, help="Max applications per run")
    parser.add_argument("--dry-run",  action="store_true",  help="Find jobs but don't submit")
    args = parser.parse_args()

    if not LI_AT:
        print("[ERROR] LINKEDIN_LI_AT env var not set.")
        sys.exit(1)

    if not Path(CV_PATH).exists():
        print(f"[WARN] CV not found at {CV_PATH}")
        print("  Run: echo $CV_BASE64 | base64 -d > " + CV_PATH)
        if not args.dry_run:
            print("  CV is required for non-dry-run. Continuing anyway (some jobs don't need it).")

    regions = list(REGION_CONFIGS.keys()) if args.region == "all" else [args.region.lower()]
    roles   = SEARCH_ROLES if args.role == "all" else [args.role]

    existing_tracker = load_tracker()
    applied_urls = {url for url, row in existing_tracker.items() if row.get("status") == "applied"}

    applied_count = 0
    skipped_count = 0
    error_count   = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        # Inject LinkedIn session cookie
        context.add_cookies([{
            "name":   "li_at",
            "value":  LI_AT,
            "domain": ".linkedin.com",
            "path":   "/",
            "secure": True,
        }])

        page = context.new_page()

        # Verify we're logged in
        page.goto("https://www.linkedin.com/feed/", timeout=30000)
        page.wait_for_timeout(2000)
        if "login" in page.url or "authwall" in page.url:
            print("[ERROR] LinkedIn session expired — li_at cookie is invalid or expired.")
            print("  Refresh your li_at cookie from browser dev tools and update the Railway env var.")
            browser.close()
            sys.exit(1)

        print(f"\n✓ Logged into LinkedIn as {P['personal']['name']}")
        print(f"  Mode    : {'DRY RUN' if args.dry_run else 'LIVE — WILL SUBMIT'}")
        print(f"  Regions : {', '.join(regions)}")
        print(f"  Max     : {args.max} applications\n")

        for region in regions:
            cfg = REGION_CONFIGS.get(region)
            if not cfg:
                print(f"[SKIP] Unknown region: {region}")
                continue

            for role in roles:
                if applied_count >= args.max:
                    break

                print(f"[Searching] {role.title()} in {cfg['location']}...")
                jobs = search_linkedin_jobs(page, role, cfg["geo_id"], cfg["location"])
                print(f"  Found {len(jobs)} Easy Apply jobs")

                for job in jobs:
                    if applied_count >= args.max:
                        break

                    job["region"] = region
                    url = job["url"]

                    # Skip already applied
                    if any(url[:60] in k for k in applied_urls):
                        skipped_count += 1
                        continue

                    print(f"  → #{applied_count+1} {job['title']} @ {job['company']}")

                    result = apply_to_job(
                        page, url, job["title"], job["company"],
                        dry_run=args.dry_run
                    )

                    if result == "applied":
                        print(f"    ✓ Applied!")
                        job["status"] = "applied"
                        job["notes"]  = f"LinkedIn Easy Apply | {datetime.now().strftime('%Y-%m-%d')}"
                        add_to_tracker(job)
                        applied_urls.add(url[:60])
                        applied_count += 1
                    elif result == "dry_run":
                        print(f"    ○ [DRY RUN] Would apply")
                        applied_count += 1
                    elif result == "skipped":
                        skipped_count += 1
                    else:
                        print(f"    ✗ {result}")
                        error_count += 1

                    # Polite delay between applications
                    time.sleep(random.uniform(3, 7))

        browser.close()

    print(f"\n{'='*50}")
    print(f"  Applied  : {applied_count}")
    print(f"  Skipped  : {skipped_count}")
    print(f"  Errors   : {error_count}")
    print(f"  Logs     : {LOG_DIR}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
