#!/usr/bin/env bash
# Install Playwright + Chromium inside the Railway container
# Run once: bash /data/workspace/job_search/scripts/install_playwright.sh
set -e

echo "=== Installing Playwright + Chromium ==="
echo "This takes ~3-5 minutes and uses ~300MB of disk."
echo ""

# Install Python playwright package
pip3 install --quiet playwright

# Install Chromium and its system dependencies
playwright install chromium
playwright install-deps chromium

# Decode CV from env var if present
if [ -n "$CV_BASE64" ]; then
    echo ""
    echo "Decoding CV from CV_BASE64 env var..."
    echo "$CV_BASE64" | base64 -d > /data/workspace/job_search/Krish_Sawhney_CV.pdf
    echo "  ✓ CV saved to /data/workspace/job_search/Krish_Sawhney_CV.pdf"
    ls -lh /data/workspace/job_search/Krish_Sawhney_CV.pdf
else
    echo ""
    echo "[WARN] CV_BASE64 env var not set — CV not decoded."
    echo "  Set it in Railway Variables (base64 of your PDF) then re-run this script."
fi

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
