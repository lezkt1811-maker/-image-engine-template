#!/usr/bin/env bash
# Copy the client's uploaded pictures from R2 into images/ so build.py can read them.
# Runs on the GitHub Actions runner only; images/ is never committed.
# Needs R2_BUCKET_NAME and R2_ENDPOINT_URL, plus AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
# holding the R2 key pair. If R2 is not configured yet, it warns and skips.
set -euo pipefail

if [[ -z "${R2_BUCKET_NAME:-}" || -z "${R2_ENDPOINT_URL:-}" ]]; then
  echo "::warning::R2 is not configured (R2_BUCKET_NAME / R2_ENDPOINT_URL). Skipping sync."
  exit 0
fi

mkdir -p images
aws s3 sync "s3://${R2_BUCKET_NAME}" images/ \
  --endpoint-url "${R2_ENDPOINT_URL}" \
  --delete \
  --exclude "*" \
  --include "*.jpg" --include "*.jpeg" --include "*.png" --include "*.webp"

echo "Synced $(find images -maxdepth 1 -type f | wc -l) picture(s) from R2."
