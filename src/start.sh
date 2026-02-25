#!/usr/bin/env bash
# Container entrypoint — starts cron then the OpenClaw server

# Start cron daemon (for daily job search at 09:00 IST / 03:30 UTC)
service cron start

# Start the OpenClaw server
exec node src/server.js
