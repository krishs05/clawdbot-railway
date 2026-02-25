#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Daily job search cron — run this every morning for fresh leads
# To schedule inside the container (via SSH):
#   crontab -e
#   0 7 * * * bash /data/workspace/job_search/scripts/run_daily.sh >> /data/workspace/job_search/daily.log 2>&1
# ─────────────────────────────────────────────────────────────────────────────
set -e

WORKSPACE="${OPENCLAW_WORKSPACE_DIR:-/data/workspace}"
JOB_DIR="$WORKSPACE/job_search"
LOG="$JOB_DIR/daily.log"

echo "======================================" | tee -a "$LOG"
echo "Daily run: $(date -u '+%Y-%m-%d %H:%M UTC')" | tee -a "$LOG"
echo "======================================" | tee -a "$LOG"

# Search all regions
python3 "$JOB_DIR/scripts/search_jobs.py" 2>&1 | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "Generating cover letters for new jobs..." | tee -a "$LOG"

# Generate cover letters
python3 "$JOB_DIR/scripts/apply.py" 2>&1 | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "── Current Status ──" | tee -a "$LOG"
python3 "$JOB_DIR/scripts/apply.py" --list 2>&1 | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "Done. Check $JOB_DIR/tracker.csv for all leads." | tee -a "$LOG"
echo "      Check $JOB_DIR/applications/ for drafts." | tee -a "$LOG"
