#!/usr/bin/env python3
"""Write the landing page (fdroid/index.html) from the built F-Droid index.

Usage: build_landing.py --index <repo/index-v2.json> --out <index.html>

One row per app: name, package id, latest version (highest versionCode in repo/), summary,
and source link, all from the signed index fdroid just built. All metadata text is
HTML-escaped. Served at https://apps.danielrosehill.com/fdroid/ (see build.sh for why it is
uploaded twice).
"""
import argparse
import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path

REPO = "https://apps.danielrosehill.com/fdroid/repo"
FPR = "35E988F3234F668852138206EB237FCF3F1FA3F4981077DE1B269E81BE1B74E7"
ADD_LINK = f"https://fdroid.link/#{REPO}?fingerprint={FPR}"
HEBRISH_REPO = "https://fdroid.hebrish.app/repo"
HEBRISH_FPR = "EF8C2D63D994A10CD489A978585510B47E47452EC09248591CB2C0F39C2BC1FA"


def loc(value):
    """Pick a localised string from an index-v2 {locale: text} map."""
    if isinstance(value, dict):
        for key in ("en-US", "en", "en-GB"):
            if value.get(key):
                return value[key]
        return next(iter(value.values()), "")
    return value or ""


def link(url, text=None):
    return f'<a href="{escape(url, quote=True)}">{escape(text or url)}</a>'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    index = json.loads(Path(args.index).read_text())
    repo_name = loc(index["repo"].get("name")) or "Daniel Rosehill Apps"
    repo_desc = loc(index["repo"].get("description"))

    apps = []
    for pkg, entry in index.get("packages", {}).items():
        meta = entry.get("metadata", {})
        versions = [v["manifest"] for v in entry.get("versions", {}).values()]
        latest = max(versions, key=lambda m: m.get("versionCode", 0)) if versions else {}
        apps.append((loc(meta.get("name")) or pkg, pkg, latest.get("versionName", ""),
                     loc(meta.get("summary")), meta.get("sourceCode", "")))
    apps.sort(key=lambda a: a[0].lower())

    rows = []
    for name, pkg, version, summary, source in apps:
        src = link(source, source.removeprefix("https://github.com/")) if source else ""
        rows.append(
            "<tr>"
            f"<td><strong>{escape(name)}</strong></td>"
            f"<td><code>{escape(pkg)}</code></td>"
            f"<td>{escape(version)}</td>"
            f"<td>{escape(summary)}</td>"
            f"<td>{src}</td>"
            "</tr>"
        )

    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(repo_name)} (F-Droid repository)</title>
<meta name="description" content="{escape(repo_desc, quote=True)}">
<style>
:root {{ --bg:#fff; --fg:#1b1f24; --muted:#59636e; --line:#d1d9e0; --code:#f2f4f7; --accent:#0b5cad; --btn-fg:#fff; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#0f1115; --fg:#e6e8eb; --muted:#9aa4af; --line:#2c323a; --code:#1a1e24; --accent:#6cb2ff; --btn-fg:#0f1115; }}
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; }}
main {{ max-width:960px; margin:0 auto; padding:32px 16px 64px; }}
h1 {{ font-size:1.6rem; margin:0 0 4px; }}
h2 {{ font-size:1.15rem; margin:32px 0 8px; }}
p.lede {{ color:var(--muted); margin:0 0 24px; }}
a {{ color:var(--accent); }}
.btn {{ display:inline-block; background:var(--accent); color:var(--btn-fg); text-decoration:none; font-weight:600; padding:10px 18px; border-radius:6px; margin:0 12px 8px 0; }}
code {{ font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:.9em; }}
.addr {{ background:var(--code); border:1px solid var(--line); border-radius:6px; padding:10px 12px; overflow-wrap:anywhere; word-break:break-all; }}
.table {{ overflow-x:auto; }}
table {{ border-collapse:collapse; width:100%; font-size:.95rem; }}
th, td {{ text-align:left; vertical-align:top; padding:8px 10px; border-bottom:1px solid var(--line); }}
th {{ color:var(--muted); font-weight:600; }}
td code {{ white-space:nowrap; }}
.note {{ border-left:3px solid var(--accent); padding:4px 12px; margin:24px 0; }}
footer {{ color:var(--muted); font-size:.85rem; margin-top:40px; }}
</style>
</head>
<body>
<main>
<h1>{escape(repo_name)}</h1>
<p class="lede">{escape(repo_desc)}</p>

<p><a class="btn" href="{escape(ADD_LINK, quote=True)}">Add to F-Droid</a>{link(REPO + "/index.html", "QR code and app list")}</p>
<p>Opens in F-Droid, Droid-ify or Neo Store on an Android phone. On a computer, scan the QR code on the app-list page with the phone instead.</p>

<h2>Add it by hand</h2>
<p>In your F-Droid client, add a repository with this address:</p>
<div class="addr"><code>{REPO}</code></div>
<p>Signing key fingerprint (SHA-256), which the client checks:</p>
<div class="addr"><code>{FPR}</code></div>

<h2>Apps</h2>
<div class="table"><table>
<thead><tr><th>App</th><th>Package</th><th>Latest</th><th>Summary</th><th>Source</th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody>
</table></div>

<div class="note"><p><strong>Hebrish moved.</strong> Hebrish (<code>app.hebrish.dictation</code>) has its own F-Droid repository, which also carries Hebrish Keyboard, and was removed from this one on 2026-10-21. If you installed it from here, F-Droid keeps the app but shows no further updates for it; add the Hebrish repository to keep getting them ({link("https://hebrish.app/download#fdroid", "instructions")}):</p>
<div class="addr"><code>{HEBRISH_REPO}</code></div>
<p>Fingerprint:</p>
<div class="addr"><code>{HEBRISH_FPR}</code></div></div>

<p>Linux desktop apps: the sibling {link("https://apps.danielrosehill.com/apt/", "APT repository")}.</p>

<footer>Index built {built}. Source: {link("https://github.com/danielrosehill/F-Droid-Public-Repo", "danielrosehill/F-Droid-Public-Repo")} · {link("https://danielrosehill.com")}</footer>
</main>
</body>
</html>
"""
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(html)


if __name__ == "__main__":
    main()
