#!/bin/bash
# Claude Status Hub - Hook script
# Sends status updates to the hub's HTTP server.
# Usage: notify.sh <status>
# Status: thinking | running | idle | closed
#
# Environment variables used:
#   CLAUDE_SESSION_ID  - unique session identifier (set by wrapper or fallback to PID)
#   CLAUDE_PROJECT_DIR - project directory (set by Claude Code)

STATUS="${1:-idle}"
SESSION_ID="${CLAUDE_SESSION_ID:-$$}"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
HUB_URL="http://127.0.0.1:5111"

curl -s -X POST "$HUB_URL" \
  -H "Content-Type: application/json" \
  -d "{\"session\":\"$SESSION_ID\", \"status\":\"$STATUS\", \"path\":\"$PROJECT_DIR\"}" \
  > /dev/null 2>&1 &

exit 0
