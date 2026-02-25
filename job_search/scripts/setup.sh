#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Job Search Automation — Container Setup Script
# Run this ONCE inside the Railway container after git pull
#
# Inside container (via SSH):
#   bash /data/workspace/job_search/scripts/setup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

WORKSPACE="${OPENCLAW_WORKSPACE_DIR:-/data/workspace}"
JOB_DIR="$WORKSPACE/job_search"

echo "=== Job Search Setup ==="
echo "Workspace: $WORKSPACE"
echo "Job dir  : $JOB_DIR"
echo ""

# Pull latest code from git if workspace is a git repo
if [ -d "$WORKSPACE/.git" ]; then
  echo "[1/4] Pulling latest code..."
  git -C "$WORKSPACE" pull --ff-only || echo "  (skip — not a clean git state)"
else
  echo "[1/4] Not a git repo — skipping pull"
fi

# Install Python dependencies (all stdlib — no pip needed for core scripts)
# Only needed if you add optional extras
echo "[2/4] Checking Python..."
python3 --version

# Create required directories
echo "[3/4] Creating directories..."
mkdir -p "$JOB_DIR/leads"
mkdir -p "$JOB_DIR/cover_letters"
mkdir -p "$JOB_DIR/applications"

# Verify profile exists
echo "[4/4] Verifying profile..."
if [ -f "$JOB_DIR/profile.json" ]; then
  echo "  ✓ profile.json found"
  python3 -c "import json; p=json.load(open('$JOB_DIR/profile.json')); print(f'  Name: {p[\"personal\"][\"name\"]}')"
else
  echo "  ✗ profile.json NOT found — something went wrong with git pull"
  exit 1
fi

echo ""
echo "=== Setup complete! ==="
echo ""
echo "── Next Steps ───────────────────────────────────────────────"
echo ""
echo "1. Search for jobs (all regions):"
echo "   python3 $JOB_DIR/scripts/search_jobs.py"
echo ""
echo "2. Search specific region:"
echo "   python3 $JOB_DIR/scripts/search_jobs.py --region uk"
echo "   python3 $JOB_DIR/scripts/search_jobs.py --region uae"
echo "   python3 $JOB_DIR/scripts/search_jobs.py --region india"
echo "   python3 $JOB_DIR/scripts/search_jobs.py --region germany"
echo ""
echo "3. Generate cover letters + application drafts:"
echo "   python3 $JOB_DIR/scripts/apply.py"
echo ""
echo "4. List all found jobs:"
echo "   python3 $JOB_DIR/scripts/apply.py --list"
echo ""
echo "5. Mark a job as applied (e.g., job #3):"
echo "   python3 $JOB_DIR/scripts/apply.py --mark-applied 3"
echo ""
echo "── Optional: Set API keys for more results ──────────────────"
echo ""
echo "  Adzuna (free — https://developer.adzuna.com):"
echo "    export ADZUNA_APP_ID=your_id"
echo "    export ADZUNA_APP_KEY=your_key"
echo ""
echo "  Reed UK (free — https://www.reed.co.uk/developers/jobseeker):"
echo "    export REED_API_KEY=your_key"
echo ""
echo "  Add these to Railway Variables to persist across deploys."
echo "─────────────────────────────────────────────────────────────"
