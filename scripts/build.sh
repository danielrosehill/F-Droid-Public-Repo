#!/usr/bin/env bash
# Rebuild and publish the F-Droid repo. Runs in CI (.github/workflows/publish.yml) and
# locally the same way.
#
# Env: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (R2 token scoped to apps-public),
#      R2_ACCOUNT_ID, FDROID_KEYSTORE_PASS, GH_TOKEN; keystore.p12 in the repo root.
#      FORCE=1 rebuilds the index even when no new release was found.
set -euo pipefail
cd "$(dirname "$0")/.."

BUCKET=s3://apps-public/fdroid
export AWS_DEFAULT_REGION=auto
S3=(aws s3 --endpoint-url "https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com" --only-show-errors)

# 1. What is already published (repo + archive).
mkdir -p tmp
: > tmp/existing.txt
for d in repo archive; do
  "${S3[@]}" ls "$BUCKET/$d/" 2>/dev/null | awk '{print $4}' | grep '\.apk$' >> tmp/existing.txt || true
done

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
for d in repo archive; do
  "${S3[@]}" sync "$d/" "$BUCKET/$d/" --exclude 'index*' --exclude 'entry*' --exclude 'diff/*'
  "${S3[@]}" sync "$d/" "$BUCKET/$d/" --delete
done
echo "Published $staged new APK(s)."
