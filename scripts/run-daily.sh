#!/bin/bash
set -e

cd "$(dirname "$0")/.."
set -a; source config/.env; set +a

SUBSCRIBER="${SUBSCRIBER_NAME:?Set SUBSCRIBER_NAME in config/.env}"

# Generate email: prompt + subscriber profile as context
OUTPUT=$(python3 scripts/generate.py prompts/daily-email.txt "subscribers/${SUBSCRIBER}/${SUBSCRIBER}.md")

# Parse subject and body
SUBJECT=$(echo "$OUTPUT" | grep "^SUBJECT:" | sed 's/^SUBJECT: //')
BODY=$(echo "$OUTPUT" | awk '/^---$/{found=1; next} found{print}')

# Write body to temp file and send
TMP=$(mktemp)
echo "$BODY" > "$TMP"
python3 scripts/send-email.py "$SUBJECT" "$TMP"
rm "$TMP"
