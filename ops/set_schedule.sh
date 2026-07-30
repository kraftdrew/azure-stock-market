#!/usr/bin/env bash
set -Eeuo pipefail

STATE="${1:-ENABLED}"
AWS_REGION="${AWS_REGION:-us-east-1}"

if [[ "$STATE" != "ENABLED" && "$STATE" != "DISABLED" ]]; then
  echo "Usage: $0 [ENABLED|DISABLED]" >&2
  exit 2
fi

aws scheduler update-schedule \
  --region "$AWS_REGION" \
  --name aws-stock-market-daily \
  --state "$STATE" \
  --flexible-time-window '{"Mode":"OFF"}' \
  --schedule-expression 'cron(0 3 * * ? *)' \
  --schedule-expression-timezone America/Toronto \
  --target "$(aws scheduler get-schedule \
    --region "$AWS_REGION" \
    --name aws-stock-market-daily \
    --query Target \
    --output json)"

echo "Daily 03:00 America/Toronto schedule state: $STATE"
