# Job Search Automation — Krish Sawhney

Automated job hunting across UK, UAE, Europe, and India.
All scripts run directly inside the Railway container via SSH.

## Quick Start (inside SSH session)

```bash
# 1. Pull latest files
cd /data/workspace && git pull

# 2. Run setup (creates dirs, verifies profile)
bash job_search/scripts/setup.sh

# 3. Search for jobs across all regions
python3 job_search/scripts/search_jobs.py

# 4. Generate cover letters + application drafts
python3 job_search/scripts/apply.py

# 5. See what's ready to apply to
python3 job_search/scripts/apply.py --list
```

## Directory Structure

```
job_search/
├── profile.json          ← Your CV details, skills, target roles
├── tracker.csv           ← Master list of all found jobs + status
├── README.md             ← This file
├── scripts/
│   ├── search_jobs.py    ← Searches Adzuna, RemoteOK, Remotive, Reed
│   ├── apply.py          ← Generates cover letters + application drafts
│   ├── setup.sh          ← One-time setup inside container
│   └── run_daily.sh      ← Daily cron script
├── leads/                ← JSON snapshots of each search run
├── cover_letters/        ← Generated cover letters (.txt)
└── applications/         ← Full application drafts with all form fields
```

## Job Sources

| Source     | Regions              | API Key Required? |
|------------|----------------------|-------------------|
| Adzuna     | UK, UAE, IN, DE, NL  | Optional (free tier without key, more results with) |
| RemoteOK   | Global Remote        | No                |
| Remotive   | Global Remote        | No                |
| Reed.co.uk | UK                   | Yes (free signup) |

## Application Workflow

```
found → cover_ready → applied → [interviewing / rejected / offer]
```

1. `search_jobs.py` adds jobs with status `found`
2. `apply.py` generates cover letters → sets status to `cover_ready`
3. You open the draft, review, click the URL → apply
4. Run `apply.py --mark-applied <ID>` to update tracker

## Searching by Region or Role

```bash
# UK only
python3 job_search/scripts/search_jobs.py --region uk

# UAE only
python3 job_search/scripts/search_jobs.py --region uae

# India only
python3 job_search/scripts/search_jobs.py --region india

# Germany only
python3 job_search/scripts/search_jobs.py --region germany

# Remote only
python3 job_search/scripts/search_jobs.py --region remote

# Specific role
python3 job_search/scripts/search_jobs.py --role "junior ai engineer"

# Generate cover letter for specific job ID
python3 job_search/scripts/apply.py --id 7

# Mark job #7 as applied
python3 job_search/scripts/apply.py --mark-applied 7
```

## Optional: Get More Results with Free API Keys

### Adzuna (highly recommended — covers all your regions)
1. Sign up free at https://developer.adzuna.com
2. In Railway dashboard → Variables → add:
   - `ADZUNA_APP_ID` = your app id
   - `ADZUNA_APP_KEY` = your app key

### Reed.co.uk (UK roles)
1. Sign up free at https://www.reed.co.uk/developers/jobseeker
2. In Railway dashboard → Variables → add:
   - `REED_API_KEY` = your key

## Daily Automation (inside container via SSH)

```bash
# Set up a daily cron at 7am UTC
crontab -e
# Add this line:
0 7 * * * bash /data/workspace/job_search/scripts/run_daily.sh >> /data/workspace/job_search/daily.log 2>&1
```

## Your Profile

- **Name**: Krish Sawhney
- **Target Roles**: Junior AI Engineer, Fullstack Developer, Junior Software Developer, Junior ML Engineer
- **Regions**: UK, Europe (DE, NL, IE), UAE, India
- **Work Mode**: Hybrid preferred, Onsite OK
- **Visa**: Sponsorship required (UK/EU/UAE), no visa needed for India
- **Notice**: 30 days
