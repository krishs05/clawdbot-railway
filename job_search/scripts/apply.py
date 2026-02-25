#!/usr/bin/env python3
"""
Application Prep + Cover Letter Generator for Krish Sawhney
Reads tracker.csv, generates tailored cover letters for 'found' jobs,
and produces ready-to-use application drafts.

Usage (inside Railway container):
  # Generate cover letters for all 'found' jobs
  python3 /data/workspace/job_search/scripts/apply.py

  # Generate for a specific job ID
  python3 /data/workspace/job_search/scripts/apply.py --id 5

  # Mark a job as applied
  python3 /data/workspace/job_search/scripts/apply.py --mark-applied 5

  # List all jobs by status
  python3 /data/workspace/job_search/scripts/apply.py --list
"""

import json
import csv
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR    = Path(__file__).parent
JOB_DIR       = SCRIPT_DIR.parent
PROFILE_PATH  = JOB_DIR / "profile.json"
TRACKER_PATH  = JOB_DIR / "tracker.csv"
COVERS_DIR    = JOB_DIR / "cover_letters"
DRAFTS_DIR    = JOB_DIR / "applications"
COVERS_DIR.mkdir(exist_ok=True)
DRAFTS_DIR.mkdir(exist_ok=True)

with open(PROFILE_PATH) as f:
    P = json.load(f)

TRACKER_FIELDS = ["id", "date_found", "title", "company", "location", "region",
                  "source", "url", "salary", "score", "status", "cover_letter_file", "notes"]


# ── CV paragraphs for cover letters ──────────────────────────────────────────
INTRO_BASE = (
    "I am a Computer Science (Artificial Intelligence) graduate from Brunel University London "
    "with hands-on experience building production-grade AI systems, full-stack applications, "
    "and scalable ML pipelines. I am currently working as an AI Intern at IntelliDB Enterprise, "
    "where I reduce inference latency, build fine-tuning pipelines, and implement CI/CD automation "
    "for ML deployments."
)

SKILL_BLOCKS = {
    "ai": (
        "My background in Reinforcement Learning — including training Q-Learning and DQN agents "
        "with OpenAI Gym for my dissertation on urban traffic signal optimisation — gives me a "
        "strong theoretical and practical foundation in applied AI. I have also worked with LLMs "
        "including TinyLlama (on-device Android), LLaMA, Claude, and Gemini."
    ),
    "fullstack": (
        "I have built full-stack applications using TypeScript, React, React Native, Next.js, "
        "and Node.js, with PostgreSQL and Spring Boot on the backend. My production projects "
        "include a Discord AI bot serving 1,000+ users (25,000+ commands processed) and a "
        "smart recipe recommendation microservice handling 500+ requests/day."
    ),
    "infra": (
        "I have strong infrastructure skills: containerised deployments with Docker, CI/CD pipelines, "
        "and cloud experience across AWS, GCP, and Azure. At IntelliDB, I improved model-serving "
        "infrastructure to support 200+ concurrent inference requests."
    ),
    "python": (
        "Python is my primary language, used across TensorFlow, Hugging Face, SUMO simulation, "
        "Streamlit dashboards, and automation tooling. I am comfortable building everything from "
        "data pipelines to REST APIs to RL training loops."
    ),
}

CLOSE_TEMPLATE = (
    "I am eager to join {company} as {a_or_an} {title} and contribute from day one. "
    "I am available with a 30-day notice period and {visa_note}. "
    "Please find my CV attached. I look forward to hearing from you.\n\n"
    "Yours sincerely,\nKrish Sawhney\n"
    "krishsawhney0502@gmail.com | +91 8800554608\n"
    "linkedin.com/in/krish-sawhney-824416261 | github.com/krishs05"
)


def pick_skill_block(title: str) -> str:
    t = title.lower()
    if any(w in t for w in ["ai", "ml", "machine learning", "reinforcement", "llm", "nlp", "data"]):
        return SKILL_BLOCKS["ai"] + "\n\n" + SKILL_BLOCKS["infra"]
    if any(w in t for w in ["fullstack", "full-stack", "full stack", "frontend", "react", "next"]):
        return SKILL_BLOCKS["fullstack"] + "\n\n" + SKILL_BLOCKS["infra"]
    if any(w in t for w in ["backend", "node", "api", "spring", "java"]):
        return SKILL_BLOCKS["fullstack"] + "\n\n" + SKILL_BLOCKS["infra"]
    if any(w in t for w in ["python", "automation", "scripting"]):
        return SKILL_BLOCKS["python"] + "\n\n" + SKILL_BLOCKS["infra"]
    # Default: well-rounded
    return SKILL_BLOCKS["fullstack"] + "\n\n" + SKILL_BLOCKS["ai"]


def a_or_an(word: str) -> str:
    return "an" if word.strip().lower()[0] in "aeiou" else "a"


def visa_note(region: str) -> str:
    region = region.lower()
    if region in ("uk", "gb"):
        return "I require a Skilled Worker visa sponsorship"
    if region in ("de", "nl", "germany", "netherlands", "europe", "eu", "ie", "ireland", "se", "sweden"):
        return "I require EU work visa sponsorship"
    if region in ("ae", "uae", "dubai"):
        return "I require a UAE work visa"
    if region in ("in", "india"):
        return "no visa support is needed"
    return "I am open to discussing visa arrangements"


def generate_cover_letter(job: dict) -> str:
    title   = job["title"]
    company = job["company"] or "your organisation"
    region  = job.get("region", "")

    skill_para = pick_skill_block(title)
    close = CLOSE_TEMPLATE.format(
        company=company,
        a_or_an=a_or_an(title),
        title=title,
        visa_note=visa_note(region),
    )

    letter = f"""Dear Hiring Manager,

Re: Application for {title} — {company}

{INTRO_BASE}

{skill_para}

{close}"""
    return letter


def generate_draft(job: dict, cover_letter: str) -> str:
    return f"""APPLICATION DRAFT
=================
Date       : {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
Role       : {job['title']}
Company    : {job['company']}
Location   : {job['location']}
Region     : {job['region']}
Source     : {job['source']}
URL        : {job['url']}
Salary     : {job.get('salary', 'Not listed')}
Status     : {job['status']}

── APPLICANT INFO ───────────────────────────────────────────
Full Name      : Krish Sawhney
Email          : krishsawhney0502@gmail.com
Phone          : +91 8800554608
LinkedIn       : linkedin.com/in/krish-sawhney-824416261
GitHub         : github.com/krishs05
Portfolio      : bertram.co.in
Current City   : New Delhi, India
Notice Period  : 30 days
Visa Required  : Yes — sponsorship required

── COVER LETTER ─────────────────────────────────────────────
{cover_letter}

── FORM FIELDS (copy-paste these) ───────────────────────────
First Name       : Krish
Last Name        : Sawhney
Email            : krishsawhney0502@gmail.com
Phone            : +918800554608
LinkedIn Profile : https://linkedin.com/in/krish-sawhney-824416261
GitHub           : https://github.com/krishs05
Portfolio/Website: https://bertram.co.in
Current Location : New Delhi, India
Willing to Relocate: Yes
Work Authorisation: Requires sponsorship
Notice Period    : 30 days
Salary Expectation: (leave blank or enter "open to discussion")

── KEY SKILLS TO TICK ON FORMS ──────────────────────────────
Python, TypeScript, JavaScript, Node.js, React, Next.js,
TensorFlow, Hugging Face, Docker, PostgreSQL, CI/CD, AWS, GCP

── EDUCATION ────────────────────────────────────────────────
Degree     : BSc Computer Science (Artificial Intelligence)
University : Brunel University London
Years      : 2022-2025

── APPLY NOW ────────────────────────────────────────────────
Open this URL in your browser to apply:
{job['url']}
"""


# ── Tracker I/O ───────────────────────────────────────────────────────────────
def load_tracker() -> list[dict]:
    if not TRACKER_PATH.exists():
        print("[ERROR] tracker.csv not found. Run search_jobs.py first.")
        sys.exit(1)
    with open(TRACKER_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_tracker(rows: list[dict]):
    with open(TRACKER_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRACKER_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


# ── Commands ──────────────────────────────────────────────────────────────────
def cmd_list(rows: list[dict]):
    statuses = {}
    for r in rows:
        statuses.setdefault(r["status"], []).append(r)

    for status, jobs in statuses.items():
        print(f"\n── {status.upper()} ({len(jobs)}) ───────────────────────────────")
        for j in jobs:
            cl = f"  [CL: {j['cover_letter_file']}]" if j.get("cover_letter_file") else ""
            print(f"  #{j['id']:>3} [{j['region'].upper():^5}] {j['title'][:40]:<40} | {j['company'][:25]:<25}{cl}")


def cmd_generate(rows: list[dict], job_id: str | None):
    targets = [r for r in rows if r["status"] == "found"] if not job_id else \
              [r for r in rows if r["id"] == job_id]

    if not targets:
        print(f"[INFO] No jobs to process." + (f" ID={job_id} not found or wrong status." if job_id else ""))
        return

    print(f"\nGenerating cover letters for {len(targets)} job(s)...\n")
    for job in targets:
        letter  = generate_cover_letter(job)
        draft   = generate_draft(job, letter)

        safe_name = f"{job['id']}_{job['company'].replace(' ', '_')[:20]}_{job['title'].replace(' ', '_')[:20]}"
        cl_file   = COVERS_DIR / f"{safe_name}_cover.txt"
        draft_file = DRAFTS_DIR / f"{safe_name}_draft.txt"

        cl_file.write_text(letter, encoding="utf-8")
        draft_file.write_text(draft, encoding="utf-8")

        # Update tracker
        for r in rows:
            if r["id"] == job["id"]:
                r["cover_letter_file"] = str(cl_file)
                r["status"] = "cover_ready"
                break

        print(f"  ✓ #{job['id']} {job['title']} @ {job['company']}")
        print(f"    Cover : {cl_file}")
        print(f"    Draft : {draft_file}\n")

    save_tracker(rows)
    print(f"Tracker updated → {TRACKER_PATH}")


def cmd_mark_applied(rows: list[dict], job_id: str):
    found = False
    for r in rows:
        if r["id"] == job_id:
            r["status"] = "applied"
            r["notes"] += f" | Applied {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
            found = True
            print(f"✓ #{job_id} marked as applied: {r['title']} @ {r['company']}")
            break
    if not found:
        print(f"[ERROR] Job ID {job_id} not found.")
        return
    save_tracker(rows)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id",           help="Process a specific job ID only")
    parser.add_argument("--list",         action="store_true", help="List all jobs by status")
    parser.add_argument("--mark-applied", metavar="ID",        help="Mark a job as applied")
    args = parser.parse_args()

    rows = load_tracker()

    if args.list:
        cmd_list(rows)
    elif args.mark_applied:
        cmd_mark_applied(rows, args.mark_applied)
    else:
        cmd_generate(rows, args.id)


if __name__ == "__main__":
    main()
