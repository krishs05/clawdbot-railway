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
    # Re-exec under the venv Python if available
    venv_py = "/data/playwright-venv/bin/python3"
    if os.path.exists(venv_py) and sys.executable != venv_py:
        os.execv(venv_py, [venv_py] + sys.argv)
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

LI_AT         = os.environ.get("LINKEDIN_LI_AT", "")
CV_PATH       = os.environ.get("CV_PATH", str(JOB_DIR / "Krish_Sawhney_CV.pdf"))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

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


# ── Gemini helpers for AI-powered form answers ───────────────────────────────
def _call_gemini(prompt: str) -> str | None:
    """Call Gemini REST API, return text or None on failure."""
    if not GEMINI_API_KEY:
        return None
    import urllib.request
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-3-flash-preview:generateContent?key={GEMINI_API_KEY}"
    )
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 200, "temperature": 0.4},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return None


_GEMINI_FORM_CACHE: dict[str, str] = {}


def _gemini_form_answer(question: str) -> str | None:
    """Use Gemini to answer an open-ended job application form question."""
    if not GEMINI_API_KEY:
        return None
    if question in _GEMINI_FORM_CACHE:
        return _GEMINI_FORM_CACHE[question]

    prompt = (
        f"You are filling out a job application form for Krish Sawhney applying for a junior "
        f"software/AI engineering role.\n\n"
        f"Form question: \"{question}\"\n\n"
        f"Candidate facts:\n"
        f"- BSc Computer Science (AI), Brunel University London, 2022-2025\n"
        f"- AI Intern at IntelliDB: ML pipelines, reduced inference latency 28%, CI/CD automation\n"
        f"- Skills: Python, TypeScript, React, Node.js, TensorFlow, Hugging Face, Docker, AWS\n"
        f"- Dissertation: RL traffic signal optimisation (Q-Learning, DQN, OpenAI Gym)\n"
        f"- 1 year experience, 30-day notice, based in New Delhi, requires visa sponsorship\n\n"
        f"Reply with ONLY the answer (1-3 sentences, first person, professional). No preamble."
    )
    answer = _call_gemini(prompt)
    if answer:
        _GEMINI_FORM_CACHE[question] = answer
    return answer


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

    # Gemini fallback — answer open-ended text/textarea questions
    if GEMINI_API_KEY and label_text.strip() and len(label_text.strip()) > 3:
        try:
            tag = input_el.evaluate("el => el.tagName.toLowerCase()")
            input_type = (input_el.get_attribute("type") or "text").lower()
            if tag == "textarea" or (tag == "input" and input_type in ("text", "")):
                ai_answer = _gemini_form_answer(label_text.strip())
                if ai_answer:
                    input_el.fill(ai_answer[:2000])
                    return True
        except Exception:
            pass

    return False


# ── JS helpers for button detection (robust across LinkedIn DOM changes) ───────
_FIND_NAV_BTN_JS = """() => {
    // Find the primary action button in the Easy Apply modal footer.
    // LinkedIn uses aria-labels, but they vary; also match by visible text.
    const SUBMIT_LABELS  = ['submit application', 'submit'];
    const REVIEW_LABELS  = ['review your application', 'review'];
    const NEXT_LABELS    = ['continue to next step', 'next', 'continue', 'next step'];

    // Only consider visible, enabled buttons
    const allBtns = Array.from(document.querySelectorAll('button')).filter(b => {
        const r = b.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && !b.disabled;
    });

    function matchBtn(labels) {
        return allBtns.find(b => {
            const al  = (b.getAttribute('aria-label') || '').toLowerCase().trim();
            const txt = b.innerText.toLowerCase().trim();
            return labels.some(l => al === l || txt === l || al.startsWith(l) || txt.startsWith(l));
        });
    }

    const submit = matchBtn(SUBMIT_LABELS);
    if (submit) return {action: 'submit', label: submit.getAttribute('aria-label') || submit.innerText.trim(), debug: null};

    const review = matchBtn(REVIEW_LABELS);
    if (review) return {action: 'review', label: review.getAttribute('aria-label') || review.innerText.trim(), debug: null};

    const next = matchBtn(NEXT_LABELS);
    if (next) return {action: 'next', label: next.getAttribute('aria-label') || next.innerText.trim(), debug: null};

    // Fallback: look for a primary/footer button in the modal that isn't Back/Close/Dismiss
    const SKIP_LABELS = ['back', 'close', 'dismiss', 'discard', 'cancel', 'exit'];
    const modal = document.querySelector('.jobs-easy-apply-modal, div[role="dialog"]');
    if (modal) {
        const footer = modal.querySelector('footer, .jobs-easy-apply-modal__content footer, [class*="footer"]');
        const searchArea = footer || modal;
        const primaryBtn = Array.from(searchArea.querySelectorAll('button')).find(b => {
            const al  = (b.getAttribute('aria-label') || '').toLowerCase().trim();
            const txt = b.innerText.toLowerCase().trim();
            if (SKIP_LABELS.some(l => al.includes(l) || txt === l)) return false;
            const r = b.getBoundingClientRect();
            return r.width > 0 && r.height > 0 && !b.disabled && txt.length > 0;
        });
        if (primaryBtn) {
            return {action: 'next', label: primaryBtn.getAttribute('aria-label') || primaryBtn.innerText.trim(), debug: 'fallback'};
        }
    }

    // Debug: return all visible button texts so we can see what's on screen
    const debugBtns = allBtns.map(b => (b.getAttribute('aria-label') || b.innerText || '').trim()).filter(Boolean);
    return {action: null, label: null, debug: debugBtns.slice(0, 10).join(' | ')};
}"""

_CLOSE_MODAL_JS = """() => {
    const dismissLabels = ['dismiss', 'close', 'discard'];
    const btns = Array.from(document.querySelectorAll('button'));
    const btn = btns.find(b => {
        const al  = (b.getAttribute('aria-label') || '').toLowerCase();
        const txt = b.innerText.toLowerCase().trim();
        return dismissLabels.some(l => al.includes(l) || txt === l);
    });
    if (btn) { btn.click(); return true; }
    return false;
}"""


# ── Core apply function ───────────────────────────────────────────────────────
def apply_to_job(page, job_url: str, job_title: str, company: str,
                 dry_run: bool = False) -> str:
    """
    Returns: 'applied' | 'skipped' | 'dry_run' | 'error:<reason>'
    """
    log_lines = [f"[{datetime.now().isoformat()}] {job_title} @ {company}"]

    try:
        page.goto(job_url, timeout=30000)

        # Wait for the job detail panel to settle
        try:
            page.wait_for_selector(
                "button.jobs-apply-button, [aria-label*='Easy Apply'], "
                "[data-control-name='jobdetails_topcard_inapply']",
                timeout=8000
            )
        except PWTimeout:
            page.wait_for_timeout(3000)

        # Find Easy Apply button via JS (more reliable than CSS selector)
        easy_apply_btn = page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button'));
            return btns.find(b => {
                const al  = (b.getAttribute('aria-label') || '').toLowerCase();
                const txt = b.innerText.toLowerCase().trim();
                return al.includes('easy apply') || txt === 'easy apply';
            }) || null;
        }""")

        if not easy_apply_btn:
            # Double-check with Playwright selector as fallback
            el = page.query_selector("[aria-label*='Easy Apply'], button.jobs-apply-button")
            if not el:
                log_lines.append("  → No Easy Apply button — external application, skipping")
                return "skipped"
            el.click()
        else:
            # Click via JS handle
            page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('button'));
                const btn = btns.find(b => {
                    const al  = (b.getAttribute('aria-label') || '').toLowerCase();
                    const txt = b.innerText.toLowerCase().trim();
                    return al.includes('easy apply') || txt === 'easy apply';
                });
                if (btn) btn.click();
            }""")

        log_lines.append("  → Easy Apply button clicked")

        if dry_run:
            log_lines.append("  → DRY RUN — not proceeding")
            page.evaluate(_CLOSE_MODAL_JS)
            return "dry_run"

        # Wait for the Easy Apply modal to open
        try:
            page.wait_for_selector(
                ".jobs-easy-apply-modal, [data-test-modal-id], "
                "div[role='dialog']",
                timeout=6000
            )
        except PWTimeout:
            log_lines.append("  → Easy Apply modal did not open")
            return "skipped"

        page.wait_for_timeout(1000)

        # Verify the dialog actually contains Easy Apply form content —
        # not just a nav dropdown or unrelated overlay that happens to be role=dialog
        has_form_content = page.evaluate("""() => {
            const selectors = [
                '.jobs-easy-apply-modal',
                '[data-test-modal-id]',
                'div[role="dialog"]',
            ];
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (!el) continue;
                // Must contain input fields OR a known Easy Apply action button
                const hasInput = el.querySelector('input, select, textarea') !== null;
                const hasBtns  = el.querySelector(
                    'button[aria-label*="apply" i], button[aria-label*="next" i], ' +
                    'button[aria-label*="submit" i], button[aria-label*="continue" i], ' +
                    'button[aria-label*="review" i]'
                ) !== null;
                // Also accept if there's a file upload (CV step)
                const hasFile = el.querySelector('input[type="file"]') !== null;
                if (hasInput || hasBtns || hasFile) return true;
            }
            return false;
        }""")

        if not has_form_content:
            log_lines.append("  → Dialog matched but no form content (nav dropdown / external redirect)")
            return "skipped"

        # Multi-step form loop (up to 10 steps)
        for step in range(10):
            log_lines.append(f"  → Step {step + 1}")

            # Upload CV if asked
            file_inputs = page.query_selector_all("input[type='file']")
            for fi in file_inputs:
                if Path(CV_PATH).exists():
                    try:
                        fi.set_input_files(CV_PATH)
                        log_lines.append("  → Uploaded CV")
                        page.wait_for_timeout(1000)
                    except Exception:
                        pass

            # Fill text/select/radio fields
            form_groups = page.query_selector_all(
                ".jobs-easy-apply-form-section__grouping, .fb-form-element, "
                "[data-test-form-element]"
            )
            for group in form_groups:
                try:
                    label_el = group.query_selector(
                        "label, .fb-form-element-label, [data-test-form-element-label]"
                    )
                    label_text = label_el.inner_text() if label_el else ""

                    inputs = group.query_selector_all(
                        "input:not([type='hidden']):not([type='file']), select, textarea"
                    )
                    for inp in inputs:
                        answer_field(page, label_text, inp)

                    # Handle radio buttons
                    radios = group.query_selector_all("input[type='radio']")
                    if radios and label_text:
                        label_lower = label_text.lower()
                        for key, val in COMMON_ANSWERS.items():
                            if key in label_lower:
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
                    try:
                        cover_textareas[0].fill(cl)
                        log_lines.append("  → Filled cover letter")
                    except Exception:
                        pass

            page.wait_for_timeout(600)

            # Find navigation button via JS (handles any aria-label LinkedIn uses)
            nav = page.evaluate(_FIND_NAV_BTN_JS)
            log_lines.append(f"  → Nav found: {nav}")

            if nav is None or nav.get("action") is None:
                debug_btns = (nav or {}).get("debug", "")
                log_lines.append(f"  → No navigation button — visible buttons: {debug_btns}")
                break

            action = nav.get("action")

            if action == "submit":
                # Click submit via JS
                page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('button'));
                    const s = ['submit application', 'submit'];
                    const btn = btns.find(b => {
                        const al  = (b.getAttribute('aria-label') || '').toLowerCase().trim();
                        const txt = b.innerText.toLowerCase().trim();
                        return s.some(l => al === l || txt === l || al.startsWith(l) || txt.startsWith(l));
                    });
                    if (btn) btn.click();
                }""")
                page.wait_for_timeout(2500)
                log_lines.append("  ✓ Application submitted!")
                # Dismiss confirmation modal
                page.evaluate(_CLOSE_MODAL_JS)
                return "applied"

            elif action in ("review", "next"):
                page.evaluate(f"""() => {{
                    const btns = Array.from(document.querySelectorAll('button'));
                    const labels = {json.dumps(['review your application', 'review', 'continue to next step', 'next', 'continue'] if action == 'review' else ['continue to next step', 'next', 'continue'])};
                    const btn = btns.find(b => {{
                        const al  = (b.getAttribute('aria-label') || '').toLowerCase().trim();
                        const txt = b.innerText.toLowerCase().trim();
                        return labels.some(l => al === l || txt === l || al.startsWith(l) || txt.startsWith(l));
                    }});
                    if (btn) btn.click();
                }}""")
                page.wait_for_timeout(1500)

        # Didn't reach submit — close the modal cleanly
        page.evaluate(_CLOSE_MODAL_JS)
        return "error:no_submit_reached"

    except PWTimeout:
        log_lines.append("  → Timeout")
        try:
            page.evaluate(_CLOSE_MODAL_JS)
        except Exception:
            pass
        return "error:timeout"
    except Exception as e:
        log_lines.append(f"  → Exception: {e}")
        try:
            page.evaluate(_CLOSE_MODAL_JS)
        except Exception:
            pass
        return f"error:{str(e)[:80]}"
    finally:
        log_file = LOG_DIR / f"apply_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        log_file.write_text("\n".join(log_lines), encoding="utf-8")


# ── LinkedIn job search ───────────────────────────────────────────────────────
def search_linkedin_jobs(page, role: str, geo_id: str, location: str,
                         max_results: int = 25) -> list[dict]:
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

    # Wait for job cards — [data-job-id] is stable across LinkedIn DOM changes
    try:
        page.wait_for_selector("[data-job-id]", timeout=10000)
    except PWTimeout:
        # No results or page structure changed — try generic list wait
        page.wait_for_timeout(4000)

    # Scroll to load more results
    for _ in range(4):
        page.evaluate("window.scrollBy(0, window.innerHeight)")
        page.wait_for_timeout(800)

    # Extract job data via JavaScript — avoids brittle class-name selectors
    raw_jobs = page.evaluate("""() => {
        const results = [];

        // Primary: cards with data-job-id (logged-in search results page)
        const cards = document.querySelectorAll('[data-job-id]');
        cards.forEach(card => {
            const jobId = card.getAttribute('data-job-id') || card.getAttribute('data-entity-urn') || '';

            // Title: try multiple selector patterns LinkedIn has used
            const titleEl = card.querySelector(
                '.job-card-list__title, .job-card-list__title--link, ' +
                '.jobs-unified-top-card__job-title, ' +
                'a[data-control-name="job_card_title"], ' +
                '.base-search-card__title, ' +
                'strong'
            );
            const title = titleEl ? titleEl.innerText.trim() : '';

            // Company
            const compEl = card.querySelector(
                '.job-card-container__primary-description, ' +
                '.job-card-container__company-name, ' +
                '.base-search-card__subtitle, ' +
                '.artdeco-entity-lockup__subtitle'
            );
            const company = compEl ? compEl.innerText.trim() : '';

            // Location
            const locEl = card.querySelector(
                '.job-card-container__metadata-item, ' +
                '.job-search-card__location, ' +
                '.artdeco-entity-lockup__caption'
            );
            const location = locEl ? locEl.innerText.trim() : '';

            // Link
            const linkEl = card.querySelector(
                'a[href*="/jobs/view/"], a[href*="jobs/view"]'
            );
            let href = linkEl ? (linkEl.getAttribute('href') || '') : '';
            if (!href && jobId) {
                const numericId = jobId.replace(/\\D/g, '');
                if (numericId) href = '/jobs/view/' + numericId + '/';
            }

            if (title && href) {
                // Strip query string
                const cleanHref = href.split('?')[0];
                results.push({
                    title,
                    company,
                    location,
                    href: cleanHref.startsWith('http') ? cleanHref : 'https://www.linkedin.com' + cleanHref
                });
            }
        });

        // Fallback: list items in the jobs results panel
        if (results.length === 0) {
            const items = document.querySelectorAll(
                '.jobs-search-results__list-item, li.scaffold-layout__list-item'
            );
            items.forEach(item => {
                const titleEl = item.querySelector('a[id*="job-card"], a[href*="/jobs/view/"]');
                const title = titleEl ? titleEl.innerText.trim() : '';
                const href = titleEl ? (titleEl.getAttribute('href') || '').split('?')[0] : '';
                const compEl = item.querySelector('.artdeco-entity-lockup__subtitle span');
                const company = compEl ? compEl.innerText.trim() : '';
                if (title && href) {
                    results.push({
                        title,
                        company,
                        location: '',
                        href: href.startsWith('http') ? href : 'https://www.linkedin.com' + href
                    });
                }
            });
        }

        return results;
    }""")

    jobs = []
    seen_urls = set()
    for item in raw_jobs[:max_results]:
        href = item.get("href", "")
        if not href or href in seen_urls:
            continue
        seen_urls.add(href)
        jobs.append({
            "title":    item.get("title", ""),
            "company":  item.get("company", ""),
            "location": item.get("location", "") or location,
            "url":      href,
            "region":   "",
        })

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
                        print(f"    ↷ Skipped (external/no modal)")
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
