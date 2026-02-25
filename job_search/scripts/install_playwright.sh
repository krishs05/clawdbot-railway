#!/usr/bin/env bash
# Install Playwright + Chromium inside the Railway container
# Run once: bash /data/workspace/job_search/scripts/install_playwright.sh
set -e

echo "=== Installing Playwright + Chromium ==="
echo "This takes ~3-5 minutes and uses ~300MB of disk."
echo ""

# Bootstrap pip (container has python3 but not pip3 in PATH)
echo "[1/3] Installing pip..."
python3 -m ensurepip --upgrade 2>/dev/null || apt-get install -y python3-pip -qq

# Install Python playwright package
echo "[2/3] Installing Playwright..."
python3 -m pip install --quiet playwright

# Install Chromium and its system dependencies
echo "[3/3] Installing Chromium..."
python3 -m playwright install chromium
python3 -m playwright install-deps chromium

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
