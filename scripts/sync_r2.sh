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

# Give each synced file its R2 upload time, so build.py dates pictures correctly
# (the runner's download time would otherwise make every picture look new).
aws s3api list-objects-v2 --bucket "${R2_BUCKET_NAME}" --endpoint-url "${R2_ENDPOINT_URL}" \
  --query 'Contents[].[Key,LastModified]' --output text 2>/dev/null |
while IFS=$'\t' read -r key modified; do
  [[ -n "$key" && "$key" != "None" && -f "images/$key" ]] && touch -d "$modified" "images/$key"
done

echo "Synced $(find images -maxdepth 1 -type f | wc -l) picture(s) from R2."
