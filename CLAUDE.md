# Krish Sawhney — Job Search Automation

This is Krish's personal Railway deployment running OpenClaw (Claude Code server).
Workspace: `/data/workspace` (persistent volume, survives restarts).

## What this project does

Automated job application system targeting Junior AI Engineer / Junior Software Developer /
Fullstack Developer roles in UK, Germany, Netherlands, UAE, and India.

**Pipeline:**
1. `search_jobs.py` — searches Adzuna, RemoteOK, Remotive, TheMuse APIs → saves to `tracker.csv`
2. `apply.py` — generates tailored cover letters + application drafts for each job found
3. `auto_apply_linkedin.py` — Playwright + LinkedIn Easy Apply → submits applications automatically
4. Runs daily at 09:00 IST (03:30 UTC) via cron

## Key files

```
/data/workspace/job_search/
  profile.json                  # Krish's full CV data (personal info, skills, experience)
  tracker.csv                   # Master job tracker (id, title, company, status, url, ...)
  scripts/
    search_jobs.py              # API job search (Adzuna/RemoteOK/Remotive/TheMuse)
    apply.py                    # Cover letter + application draft generator
    auto_apply_linkedin.py      # Playwright LinkedIn Easy Apply bot
    run_daily.sh                # Full daily pipeline (search → cover letters → auto-apply)
    install_playwright.sh       # One-time Playwright + Chromium setup
  cover_letters/                # Generated .txt cover letters (gitignored)
  applications/                 # Generated application drafts (gitignored)
  apply_logs/                   # Per-application Playwright logs
  daily.log                     # Cron run log
  Krish_Sawhney_CV.pdf          # CV for upload during LinkedIn Easy Apply
```

## Applicant profile (Krish Sawhney)

- **Email:** krishsawhney0502@gmail.com | **Phone:** +918800554608
- **Location:** New Delhi, India | **Notice:** 30 days
- **Visa:** Requires sponsorship (UK/EU/UAE), no sponsorship needed for India
- **Education:** BSc CS (AI), Brunel University London, 2022–2025
- **LinkedIn:** linkedin.com/in/krish-sawhney-824416261
- **GitHub:** github.com/krishs05 | **Portfolio:** bertram.co.in

## Environment variables (Railway)

| Variable | Purpose |
|---|---|
| `LINKEDIN_LI_AT` | LinkedIn session cookie (`li_at`) — refresh when expired |
| `GEMINI_API_KEY` | Google Gemini API key — enables AI-generated cover letters and form question answers |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | Adzuna API credentials |
| `REED_API_KEY` | Reed.co.uk API key |
| `CV_PATH` | Optional override for CV path (default: `/data/workspace/job_search/Krish_Sawhney_CV.pdf`) |
| `PLAYWRIGHT_BROWSERS_PATH` | Set to `/data/playwright-browsers` so Chromium persists across restarts |

## Running scripts manually (via `railway ssh`)

```bash
cd /data/workspace

# 1. Search for new jobs (all regions)
python3 job_search/scripts/search_jobs.py

# 2. Generate cover letters for new jobs
python3 job_search/scripts/apply.py

# 3. List all jobs by status
python3 job_search/scripts/apply.py --list

# 4. LinkedIn auto-apply — dry run (no submissions)
/data/playwright-venv/bin/python3 job_search/scripts/auto_apply_linkedin.py --dry-run --region uk --max 5

# 5. LinkedIn auto-apply — live (UK, up to 20 jobs)
/data/playwright-venv/bin/python3 job_search/scripts/auto_apply_linkedin.py --region uk --max 20

# 6. LinkedIn auto-apply — all regions
/data/playwright-venv/bin/python3 job_search/scripts/auto_apply_linkedin.py --region all --max 50

# 7. Full daily pipeline (same as cron)
bash job_search/scripts/run_daily.sh
```

## Playwright setup (persistent volume)

Playwright venv lives at `/data/playwright-venv` (persists across restarts).
Chromium browser lives at `/data/playwright-browsers` (persists via PLAYWRIGHT_BROWSERS_PATH env).
System libs (libatk, libgbm, etc.) are baked into the Dockerfile — no reinstall needed.

If browser is missing (first deploy or `/data` wipe):
```bash
bash /data/workspace/job_search/scripts/install_playwright.sh
```

## Refreshing the li_at LinkedIn cookie

The `li_at` cookie expires every ~1–2 weeks. When auto-apply prints:
```
[ERROR] LinkedIn session expired — li_at cookie is invalid or expired.
```

1. Open LinkedIn in Chrome → F12 → Application → Cookies → `linkedin.com`
2. Copy the value of `li_at`
3. Update Railway env var `LINKEDIN_LI_AT` with the new value
4. Redeploy or restart the container

## Job tracker statuses

`found` → `cover_ready` → `applied`

## Git workflow

```bash
# Pull latest changes into container
git -C /data/workspace pull https://github.com/krishs05/clawdbot-railway.git main
```

No `Co-Authored-By: Claude` in commits.

## Cron schedule

Daily at 09:00 IST = 03:30 UTC:
```
30 3 * * * bash /data/workspace/job_search/scripts/run_daily.sh >> /data/workspace/job_search/daily.log 2>&1
```

Cron is started by `src/start.sh` on container boot (configured in Dockerfile).
