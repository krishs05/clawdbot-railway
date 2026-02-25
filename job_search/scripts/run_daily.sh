#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Daily job search + auto-apply pipeline — runs at 09:00 IST (03:30 UTC)
# Cron entry (already configured in Dockerfile):
#   30 3 * * * bash /data/workspace/job_search/scripts/run_daily.sh >> /data/workspace/job_search/daily.log 2>&1
# ─────────────────────────────────────────────────────────────────────────────
set -e

WORKSPACE="${OPENCLAW_WORKSPACE_DIR:-/data/workspace}"
JOB_DIR="$WORKSPACE/job_search"
LOG="$JOB_DIR/daily.log"
VENV="/data/playwright-venv"

echo "======================================" | tee -a "$LOG"
echo "Daily run: $(date -u '+%Y-%m-%d %H:%M UTC')" | tee -a "$LOG"
echo "======================================" | tee -a "$LOG"

# ── Step 1: Search for new jobs ───────────────────────────────────────────────
echo "" | tee -a "$LOG"
echo "[1/3] Searching job boards..." | tee -a "$LOG"
python3 "$JOB_DIR/scripts/search_jobs.py" 2>&1 | tee -a "$LOG"

# ── Step 2: Generate cover letters ───────────────────────────────────────────
echo "" | tee -a "$LOG"
echo "[2/3] Generating cover letters for new jobs..." | tee -a "$LOG"
python3 "$JOB_DIR/scripts/apply.py" 2>&1 | tee -a "$LOG"

# ── Step 3: LinkedIn Easy Apply ───────────────────────────────────────────────
echo "" | tee -a "$LOG"
echo "[3/3] LinkedIn Easy Apply (all regions, max 30)..." | tee -a "$LOG"

if [ -z "$LINKEDIN_LI_AT" ]; then
    echo "  [SKIP] LINKEDIN_LI_AT not set — skipping auto-apply" | tee -a "$LOG"
elif [ ! -f "$VENV/bin/python3" ]; then
    echo "  [SKIP] Playwright venv not found at $VENV" | tee -a "$LOG"
    echo "  Run: bash $JOB_DIR/scripts/install_playwright.sh" | tee -a "$LOG"
else
    # Ensure Chromium browser binary is present (persists in /data/playwright-browsers)
    if [ ! -d "${PLAYWRIGHT_BROWSERS_PATH:-/data/playwright-browsers}" ] || \
       [ -z "$(ls -A "${PLAYWRIGHT_BROWSERS_PATH:-/data/playwright-browsers}" 2>/dev/null)" ]; then
        echo "  [INFO] Chromium not found — installing..." | tee -a "$LOG"
        "$VENV/bin/playwright" install chromium 2>&1 | tee -a "$LOG"
    fi

    "$VENV/bin/python3" "$JOB_DIR/scripts/auto_apply_linkedin.py" \
        --region all --max 30 2>&1 | tee -a "$LOG"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo "" | tee -a "$LOG"
echo "── Current Status ──" | tee -a "$LOG"
python3 "$JOB_DIR/scripts/apply.py" --list 2>&1 | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "Done. Tracker: $JOB_DIR/tracker.csv" | tee -a "$LOG"
echo "      Drafts : $JOB_DIR/applications/" | tee -a "$LOG"
echo "      Logs   : $JOB_DIR/apply_logs/" | tee -a "$LOG"
