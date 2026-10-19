#!/usr/bin/env python3
"""Stage the newest release APK of every app in apps.yml that the bucket lacks.

Usage: sync_releases.py --existing <file of APK names already in the bucket> --dest <dir>

Writes `staged=<n>` to $GITHUB_OUTPUT (when set) and prints one line per app.
Needs `gh` authenticated (GH_TOKEN) with read access to every listed repo.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def gh_json(*args):
    return json.loads(subprocess.check_output(["gh", *args], text=True))


def pick_release(app):
    prefix = app.get("tag_prefix", "")
    suffix = app.get("asset_suffix", ".apk")
    for rel in gh_json("api", f"repos/{app['repo']}/releases?per_page=30"):
        if rel["draft"] or (rel["prerelease"] and not app.get("prereleases")):
            continue
        if not rel["tag_name"].startswith(prefix):
            continue
        apks = [a for a in rel["assets"] if a["name"].endswith(suffix)]
        if apks:
            return rel["tag_name"], apks[0]["name"]
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--existing", required=True)
    ap.add_argument("--dest", required=True)
    args = ap.parse_args()

    existing = set(Path(args.existing).read_text().split())
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    apps = yaml.safe_load((ROOT / "apps.yml").read_text())["apps"]

    staged = 0
    for app in apps:
        tag, asset = pick_release(app)
        if not tag:
            print(f"{app['repo']}: no release with an APK", file=sys.stderr)
            continue
        target = f"{app['package']}_{tag}.apk"
        if target in existing:
            print(f"{app['repo']}: {tag} already published")
            continue
        tmp = dest / ".dl"
        subprocess.check_call(["gh", "release", "download", tag, "-R", app["repo"],
                               "-p", asset, "-D", str(tmp), "--clobber"])
        (tmp / asset).rename(dest / target)
        print(f"{app['repo']}: staged {tag} as {target}")
        staged += 1

    if out := os.environ.get("GITHUB_OUTPUT"):
        with open(out, "a") as fh:
            fh.write(f"staged={staged}\n")


if __name__ == "__main__":
    main()
