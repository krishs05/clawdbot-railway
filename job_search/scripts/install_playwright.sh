#!/usr/bin/env bash
# Install Playwright + Chromium inside the Railway container
# Run once: bash /data/workspace/job_search/scripts/install_playwright.sh
set -e

echo "=== Installing Playwright + Chromium ==="
echo "This takes ~3-5 minutes and uses ~300MB of disk."
echo ""

# Create a persistent venv in /data so it survives container restarts
VENV="/data/playwright-venv"
echo "[1/3] Creating Python venv at $VENV..."
python3 -m venv "$VENV"

# Install Playwright into the venv
echo "[2/3] Installing Playwright..."
"$VENV/bin/pip" install --quiet playwright

# Install Chromium and system deps
echo "[3/3] Installing Chromium..."
"$VENV/bin/playwright" install chromium
"$VENV/bin/playwright" install-deps chromium

# Write a wrapper so scripts can call `playwright-python` without activating venv
ln -sf "$VENV/bin/python3" /usr/local/bin/playwright-python 2>/dev/null || true
echo "  VENV=$VENV" >> /data/workspace/job_search/.env_playwright

echo ""
echo "=== Done! ==="
echo ""
echo "Run a dry-run to verify everything works:"
echo "  python3 /data/workspace/job_search/scripts/auto_apply_linkedin.py --dry-run --region uk"
echo ""
echo "Run live (applies up to 20 jobs):"
echo "  python3 /data/workspace/job_search/scripts/auto_apply_linkedin.py --region uk --max 20"
echo ""
echo "Run all regions:"
echo "  python3 /data/workspace/job_search/scripts/auto_apply_linkedin.py --region all --max 50"
