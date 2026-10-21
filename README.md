# F-Droid-Public-Repo

Public [F-Droid](https://f-droid.org) repository for Daniel Rosehill's Android apps.
Static files on Cloudflare R2, rebuilt by GitHub Actions.

**Add it to F-Droid / Droid-ify / Neo Store:**

<https://fdroid.link/#https://apps.danielrosehill.com/fdroid/repo?fingerprint=35E988F3234F668852138206EB237FCF3F1FA3F4981077DE1B269E81BE1B74E7>

| | |
|---|---|
| Repo URL | `https://apps.danielrosehill.com/fdroid/repo` |
| Web page + QR | <https://apps.danielrosehill.com/fdroid/repo/index.html> |
| Signing key SHA-256 | `35E988F3234F668852138206EB237FCF3F1FA3F4981077DE1B269E81BE1B74E7` |
| Bucket | R2 `apps-public` (account `81ee9810726226b99b56e4d84ffac020`), custom domain `apps.danielrosehill.com`, prefix `fdroid/` |

## How it works

```
app repo: tag → CI builds release-signed APK → GitHub release
                                   │  (hourly cron / push / dispatch)
this repo: scripts/sync_releases.py  stages any release APK the bucket lacks
           scripts/build.sh          pulls published APKs, `fdroid update`, syncs to R2
```

- `apps.yml` lists the GitHub repos to track (`repo`, `package`, optional `tag_prefix`
  for repos that also release desktop builds). The newest non-draft release with an
  APK asset is staged as `repo/<package>_<tag>.apk`. Presence of that filename in the
  bucket (`repo/` or `archive/`) is the only state: no state file.
- `metadata/<package>.yml` holds store text (name, summary, description, links).
- `config.yml` is the fdroidserver config. Secrets come from env (`{env: ...}`).
- `archive_older: 3`: three versions per app stay in `repo/`, older ones move to
  `archive/`.
- Upload order: APKs first, index last, so a client never sees an index entry whose
  file is missing.
- The workflow commits back skeleton metadata that `fdroid update -c` writes for a
  hand-uploaded APK.

### Triggers

| Event | Rebuilds index |
|---|---|
| hourly cron | only if a new release was found |
| push to `apps.yml`, `metadata/**`, `config.yml`, `scripts/**` | always |
| `gh workflow run publish.yml -R danielrosehill/F-Droid-Public-Repo` | always (input `force`, default true) |
| `repository_dispatch` type `publish` | always |

## Adding an app

**From GitHub releases:** add an entry to `apps.yml` and a `metadata/<package>.yml`,
push. The push triggers a publish.

**One-off APK (no release):** upload it to `s3://apps-public/fdroid/repo/<package>_<version>.apk`,
add `metadata/<package>.yml`, push (or `gh workflow run publish.yml`).

The private `software-publisher` Claude plugin
(`danielrosehill/Claude-Software-Publisher-Plugin`, named `fdroid-publisher` until
2026-10-20) wraps both. Its `deb-*` skills drive the sibling APT repo,
[`APT-Public-Repo`](https://github.com/danielrosehill/APT-Public-Repo), served from the same
bucket under `apt/`.

### Requirements for an APK

- **Release-signed with a stable key.** A `CN=Android Debug` signature comes from
  whichever machine built it. The next build from a different runner has a different
  key, and Android refuses the update. Check with
  `keytool -printcert -jarfile app.apk` or `apksigner verify --print-certs`.
- `versionCode` must increase every release. An equal code with a different file
  breaks updates for installed users.
- One package id per app. `Israel-Alert-Map` and `Israel-Geomap-APK` both ship
  `com.danielrosehill.israelgeomap`, so only one of them can be listed.

## Secrets

| GitHub | Value | Source |
|---|---|---|
| secret `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` | R2 S3 token for `apps-public` | 1Password `API Keys & Programmatic` → "Public Apps R2 Bucket API Key" (`username` / `credential`) |
| secret `FDROID_KEYSTORE_B64` | base64 of the repo keystore | 1Password `Daniel - Personal` → document "Android signing key - F-Droid Repo (public)" |
| secret `FDROID_KEYSTORE_PASS` | keystore + key password (alias `fdroid-public`) | 1Password `Daniel - Personal` → "Android signing key - F-Droid Repo (public) - password" |
| variable `R2_ACCOUNT_ID` | `81ee9810726226b99b56e4d84ffac020` | |
| secret `RELEASES_READ_TOKEN` (optional) | PAT that can read private app repos' releases | not set; `github.token` reads public repos |

Local copy of the keystore: `~/.config/android-signing/fdroid-repo-public.p12` (+ `.pass`).
**Losing the repo key means every user has to remove and re-add the repo.**

`op://` references can't use the vault name `API Keys & Programmatic`. `op` rejects
the `&` as an invalid character. Use the vault id `k6bqzdeflgcb44rqc64y2p2aha`.

## Running locally

```bash
cp ~/.config/android-signing/fdroid-repo-public.p12 keystore.p12
V=k6bqzdeflgcb44rqc64y2p2aha I=4k6mo5srumwmxukh56zyu6l6ui
export AWS_ACCESS_KEY_ID=$(op read "op://$V/$I/username") AWS_SECRET_ACCESS_KEY=$(op read "op://$V/$I/credential") \
  R2_ACCOUNT_ID=81ee9810726226b99b56e4d84ffac020 \
  FDROID_KEYSTORE_PASS=$(cat ~/.config/android-signing/fdroid-repo-public.pass) GH_TOKEN=$(gh auth token)
FORCE=1 scripts/build.sh
```

Needs `fdroid` (`uv tool install fdroidserver`, 2.4.5 verified), `aws`, `gh`, and
`apksigner` under `$ANDROID_HOME/build-tools`.

## Private siblings

Two private F-Droid repos run the same scripts with a different default bucket. Both were
scaffolded on 2026-10-21 and are **not served yet**: no host, no access control, no R2
token.

| Repo | Audience | Bucket |
|---|---|---|
| [`F-Droid-Private-Repo`](https://github.com/danielrosehill/F-Droid-Private-Repo) | Daniel only | `apps-private` |
| [`F-Droid-Household-Repo`](https://github.com/danielrosehill/F-Droid-Household-Repo) (Rosehill Household Repo) | the household | `apps-household` |

Each README has a status table and the open access-control question. The leading option
is a Cloudflare Worker with HTTP basic auth, because store clients can't do a Cloudflare
Access login.

## History

- 2026-10-20: created. First publish run locally, then handed to CI. Held back as
  debug-signed: Voxcast, Driving-Checklists, Readiness-Voice-Agent, Family-Page,
  Israel-Alert-Map, Israel-Geomap-APK (details in `apps.yml`).
- 2026-10-20: moved to `apps.danielrosehill.com`. `apps.bydanielrosehill.com` still
  serves the same bucket, but the index names the new host. Fixed a "bad fingerprint"
  error on first add. Cloudflare cached the signed `entry.jar` (4 h edge TTL for
  `.jar`) but not `index-v2.json`, so their hashes disagreed after a rebuild. Index
  files are now uploaded with `Cache-Control: public, max-age=60`. Reproduce or verify
  with fdroidserver's own client code:
  `python -c "import fdroidserver.common as c, fdroidserver.index as i; c.config={'jarsigner':'/usr/bin/jarsigner'}; i.download_repo_index_v2('<repo url>?fingerprint=<fp>')"`.
- 2026-10-20, open: `apps.danielrosehill.com` used to be the Vercel `Apps-Microsite` domain.
  It now serves this bucket, so the microsite is only reachable at `apps-microsite.vercel.app`,
  and the "Apps & Tools" / "Apps" links on danielrosehill.com/projects hit a 404 at this
  host's root. Deferred by Daniel (microsite low priority). The likely fix is a Cloudflare
  redirect rule that sends everything outside `/fdroid/` to the microsite.
