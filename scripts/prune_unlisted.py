#!/usr/bin/env python3
"""Remove APKs of apps that are no longer published from this repo.

Usage:
  prune_unlisted.py --check <file of published APK names>
      Filename-only pre-check, run before anything is downloaded. Prints and writes
      `orphans=<n>`: published APKs whose name does not start with "<kept package>_".
      It never deletes anything; it only tells build.sh that a rebuild is due (so the
      hourly cron run, which otherwise exits when no release is new, still prunes).
  prune_unlisted.py --prune <dir> [<dir> ...]
      Reads each APK's real package id (fdroidserver.common.get_apk_id, so the file name
      does not matter) and deletes every APK whose package is not kept, plus anything
      fdroid generated for that package in those dirs (repo/<package>/, icons*/<package>.*).
      Prints one line per deleted file and writes `pruned=<n>`.

A package is kept when it is listed in apps.yml OR has a metadata/<package>.yml. The
second rule protects one-off hand-uploaded APKs, which have metadata but no apps.yml
entry. Safety: if apps.yml yields no packages (missing, empty or unparseable), nothing is
pruned. An APK whose id cannot be read is kept and logged.

Outputs go to $GITHUB_OUTPUT when set. --prune needs fdroidserver importable: build.sh runs
it with the interpreter of the installed `fdroid` command.
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def kept_packages():
    try:
        apps = yaml.safe_load((ROOT / "apps.yml").read_text()).get("apps") or []
        listed = {a["package"] for a in apps if a.get("package")}
    except Exception as e:  # noqa: BLE001 - any failure means "do not prune"
        print(f"prune: could not read apps.yml ({e}); pruning skipped", file=sys.stderr)
        return None
    if not listed:
        print("prune: apps.yml lists no packages; pruning skipped", file=sys.stderr)
        return None
    with_metadata = {p.stem for p in (ROOT / "metadata").glob("*.yml")}
    return listed | with_metadata


def output(key, value):
    print(f"{key}={value}")
    if out := os.environ.get("GITHUB_OUTPUT"):
        with open(out, "a") as fh:
            fh.write(f"{key}={value}\n")


def check(existing_file, keep):
    names = Path(existing_file).read_text().split()
    orphans = [n for n in names if not any(n.startswith(p + "_") for p in keep)]
    for n in orphans:
        print(f"prune: candidate {n} (package not in apps.yml or metadata/)")
    output("orphans", len(orphans))


def prune(dirs, keep):
    from fdroidserver.common import get_apk_id

    pruned = 0
    gone = set()
    for d in map(Path, dirs):
        for apk in sorted(d.glob("*.apk")):
            try:
                appid, vercode, vername = get_apk_id(str(apk))
            except Exception as e:  # noqa: BLE001
                print(f"prune: kept {apk} (could not read package id: {e})", file=sys.stderr)
                continue
            if appid in keep:
                continue
            print(f"prune: deleted {apk} ({appid} {vername}, code {vercode})")
            apk.unlink()
            gone.add(appid)
            pruned += 1
    # Files fdroid generated for a removed package (left over from an earlier local run;
    # in CI repo/ starts with APKs only). The final `aws s3 sync --delete` removes the
    # bucket copies of everything deleted here.
    for d in map(Path, dirs):
        for appid in sorted(gone):
            for p in [d / appid, *d.glob(f"icons*/{appid}.*")]:
                if p.is_dir():
                    shutil.rmtree(p)
                elif p.exists():
                    p.unlink()
                else:
                    continue
                print(f"prune: deleted {p}")
    output("pruned", pruned)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", metavar="EXISTING")
    g.add_argument("--prune", nargs="+", metavar="DIR")
    args = ap.parse_args()

    keep = kept_packages()
    if keep is None:
        output("orphans" if args.check else "pruned", 0)
        return
    if args.check:
        check(args.check, keep)
    else:
        prune(args.prune, keep)


if __name__ == "__main__":
    main()
