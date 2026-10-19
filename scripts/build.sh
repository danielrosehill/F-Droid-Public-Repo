#!/usr/bin/env bash
# Rebuild and publish the F-Droid repo. Runs in CI (.github/workflows/publish.yml) and
# locally the same way.
#
# Env: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (R2 token scoped to apps-public),
#      R2_ACCOUNT_ID, FDROID_KEYSTORE_PASS, GH_TOKEN; keystore.p12 in the repo root.
#      FORCE=1 rebuilds the index even when no new release was found.
#      R2_BUCKET overrides the bucket (default apps-public); the prefix is always fdroid/.
set -euo pipefail
cd "$(dirname "$0")/.."

R2_BUCKET=${R2_BUCKET:-apps-public}
BUCKET=s3://$R2_BUCKET/fdroid
export AWS_DEFAULT_REGION=auto
ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
S3=(aws s3 --endpoint-url "$ENDPOINT" --only-show-errors)

# 1. What is already published (repo + archive). Fails loudly: a listing error must
#    not read as "bucket empty", or every run republishes everything.
mkdir -p tmp
aws s3api list-objects-v2 --endpoint-url "$ENDPOINT" --bucket "$R2_BUCKET" --prefix fdroid/ \
  --query 'Contents[].Key' --output text > tmp/keys.txt
tr '\t' '\n' < tmp/keys.txt | grep '\.apk$' | xargs -rn1 basename > tmp/existing.txt || true
echo "$(wc -l < tmp/existing.txt) APK(s) already published"

# 2. Stage new release APKs.
GITHUB_OUTPUT=tmp/out python3 scripts/sync_releases.py --existing tmp/existing.txt --dest tmp/new
staged=$(sed -n 's/^staged=//p' tmp/out)
if [[ "$staged" == 0 && "${FORCE:-0}" != 1 ]]; then
  echo "Nothing new; index left as is."
  exit 0
fi

# 3. Pull the published APKs (fdroid rebuilds everything else from them).
mkdir -p repo/icons archive
"${S3[@]}" sync "$BUCKET/repo/" repo/ --exclude '*' --include '*.apk'
"${S3[@]}" sync "$BUCKET/archive/" archive/ --exclude '*' --include '*.apk'
mv tmp/new/*.apk repo/ 2>/dev/null || true
cp icon.png repo/icons/icon.png

# 4. Index. -c writes skeleton metadata for any APK uploaded by hand without one.
fdroid update -c --pretty

# 5. Publish: APKs and icons first, index last, so a client never sees an index
#    pointing at a file that is not there yet.
#    Index files get a 60 s Cache-Control. Without it Cloudflare's edge caches
#    entry.jar (a .jar is a default-cacheable extension) for 4 h but never caches
#    the .json, so after any rebuild clients get an old signed entry.jar beside a new
#    index-v2.json. The hash check then fails, and F-Droid reports it as a bad
#    fingerprint. Seen 2026-10-20.
INDEX=(--exclude '*' --include 'index*' --include 'entry*' --include 'diff/*')
for d in repo archive; do
  "${S3[@]}" sync "$d/" "$BUCKET/$d/" --exclude 'index*' --exclude 'entry*' --exclude 'diff/*'
  "${S3[@]}" sync "$d/" "$BUCKET/$d/" "${INDEX[@]}" --cache-control 'public, max-age=60' --exact-timestamps
  "${S3[@]}" sync "$d/" "$BUCKET/$d/" --delete
done
echo "Published $staged new APK(s)."
