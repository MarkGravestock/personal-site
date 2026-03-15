#!/usr/bin/env python3
"""
update_bookmarks.py — Fetch bookmarks from Raindrop.io and generate MkDocs pages.

Usage:
    RAINDROP_TOKEN=<token> python update_bookmarks.py

Writes:
    docs/bookmarks/posts/<date>-<slug>.md  — one page per bookmark
    docs/bookmarks/index.md               — monthly card-grid listing
"""

import json
import os
import platform
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from urllib import request, error

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RAINDROP_COLLECTION_ID = "64296840"
RAINDROP_API_URL = f"https://api.raindrop.io/rest/v1/raindrops/{RAINDROP_COLLECTION_ID}"
PAGE_SIZE = 50
TIMEOUT = 30

POSTS_DIR = "docs/bookmarks/posts"
INDEX_PATH = "docs/bookmarks/index.md"

SYSTEM_TAGS = {"article", "link", "public", "video", "image", "document", "audio"}

# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

def _day_fmt() -> str:
    """Return the platform-appropriate strftime code for a non-zero-padded day."""
    return "%#d" if platform.system() == "Windows" else "%-d"


def filter_tags(tags: list) -> list:
    """Remove Raindrop system tags, keep user tags."""
    return [t for t in tags if t.lower() not in SYSTEM_TAGS]


def generate_slug(title: str, date: str, existing_slugs: set, bookmark_id: str = "") -> str:
    """
    Generate a filename-safe slug: '<date>-<title-slug>'.
    On collision with existing_slugs, appends '-<bookmark_id>'.
    """
    slug_body = title.lower()
    slug_body = re.sub(r"[^a-z0-9]+", "-", slug_body)
    slug_body = re.sub(r"-+", "-", slug_body)
    slug_body = slug_body.strip("-")
    slug_body = slug_body[:50].rstrip("-")

    slug = f"{date}-{slug_body}"

    if slug in existing_slugs and bookmark_id:
        slug = f"{slug}-{bookmark_id}"

    return slug


def _format_date_display(date_str: str) -> str:
    """'2026-03-10' -> '10 Mar 2026'"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime(f"{_day_fmt()} %b %Y")
    except ValueError:
        return date_str


def _format_month_heading(date_str: str) -> str:
    """'2026-03-10' -> 'March 2026'"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%B %Y")
    except ValueError:
        return date_str


def _month_key(date_str: str) -> str:
    """'2026-03-10' -> '2026-03' (for grouping and sorting)"""
    return date_str[:7]


def render_bookmark_page(bm: dict) -> str:
    """Render the full Markdown content for a single bookmark page."""
    lines = ["---"]
    safe_title = bm["title"].replace('"', '\\"')
    lines.append(f'title: "{safe_title}"')
    lines.append(f'date: {bm["date"]}')

    tags = bm.get("tags", [])
    if tags:
        lines.append("tags:")
        for tag in tags:
            lines.append(f"  - {tag}")

    lines.append("---")
    lines.append("")
    lines.append(f'**[{bm["title"]}]({bm["link"]})**')
    lines.append("")
    lines.append(f'{bm["domain"]} \u00b7 {bm["date_display"]}')

    note = bm.get("note", "").strip()
    if note:
        lines.append("")
        lines.append(f"> {note}")

    lines.append("")
    return "\n".join(lines)


def render_card(bm: dict) -> str:
    """Render a single card entry for the index page card grid."""
    slug = bm["slug"]
    title = bm["title"]
    tags = bm.get("tags", [])
    domain = bm["domain"]
    date_short = datetime.strptime(bm["date"], "%Y-%m-%d").strftime(f"{_day_fmt()} %b")

    card_lines = [f"- **[{title}](posts/{slug}.md)**", ""]

    meta_parts = []
    if tags:
        meta_parts.append(" ".join(f"`#{t}`" for t in tags))
    meta_parts.append(f"{domain} \u00b7 {date_short}")

    card_lines.append(f"    {' \u00b7 '.join(meta_parts)}")
    card_lines.append("")
    return "\n".join(card_lines)


def render_index(bookmarks: list) -> str:
    """Render the full bookmarks/index.md content."""
    lines = [
        "---",
        "title: Bookmarks",
        "---",
        "# Bookmarks",
        "",
        "A collection of useful things I've found on the web.",
        "",
    ]

    by_month = defaultdict(list)
    for bm in bookmarks:
        by_month[_month_key(bm["date"])].append(bm)

    for month_key in sorted(by_month.keys(), reverse=True):
        month_bms = by_month[month_key]
        if not month_bms:
            continue
        heading = _format_month_heading(month_bms[0]["date"])
        lines.append(f"## {heading}")
        lines.append("")
        lines.append('<div class="grid cards" markdown>')
        lines.append("")
        for bm in month_bms:
            lines.append(render_card(bm))
        lines.append("</div>")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# I/O layer (API + file system + git)
# ---------------------------------------------------------------------------

def fetch_bookmarks(token: str) -> list:
    """
    Fetch all bookmarks from Raindrop API. Returns list of raw item dicts.
    Raises SystemExit on any HTTP or network error.
    """
    items = []
    page = 0

    while True:
        url = f"{RAINDROP_API_URL}?perpage={PAGE_SIZE}&page={page}"
        req = request.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
        except error.HTTPError as e:
            print(f"ERROR: Raindrop API returned {e.code} on page {page}", file=sys.stderr)
            sys.exit(1)
        except error.URLError as e:
            print(f"ERROR: Network error fetching page {page}: {e.reason}", file=sys.stderr)
            sys.exit(1)

        page_items = data.get("items", [])
        items.extend(page_items)

        if len(page_items) < PAGE_SIZE:
            break
        page += 1

    return items


def parse_bookmark(item: dict, existing_slugs: set) -> dict:
    """Convert a raw Raindrop API item into a bookmark dict."""
    title = item.get("title") or item.get("link", "Untitled")
    link = item.get("link", "")
    domain = item.get("domain", "")
    raw_tags = item.get("tags", [])
    note = item.get("note", "") or ""
    raindrop_id = str(item.get("_id", ""))

    raw_date = item.get("created", "")
    try:
        dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        date = dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        date = datetime.now().strftime("%Y-%m-%d")

    tags = filter_tags(raw_tags)
    slug = generate_slug(title, date, existing_slugs, bookmark_id=raindrop_id)
    existing_slugs.add(slug)

    date_display = datetime.strptime(date, "%Y-%m-%d").strftime(f"{_day_fmt()} %b %Y")

    return {
        "title": title,
        "link": link,
        "domain": domain,
        "tags": tags,
        "note": note.strip(),
        "date": date,
        "date_display": date_display,
        "slug": slug,
        "raindrop_id": raindrop_id,
    }


def write_bookmark_page(bm: dict) -> None:
    """Write a single bookmark page to docs/bookmarks/posts/."""
    path = os.path.join(POSTS_DIR, f'{bm["slug"]}.md')
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_bookmark_page(bm))


def write_index(bookmarks: list) -> bool:
    """Write docs/bookmarks/index.md. Returns True if content changed."""
    new_content = render_index(bookmarks)
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            existing = f.read()
    except FileNotFoundError:
        existing = ""

    if new_content == existing:
        return False

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True


def delete_existing_posts() -> None:
    """Delete all generated bookmark pages (keep .gitkeep)."""
    if not os.path.isdir(POSTS_DIR):
        return
    for fname in os.listdir(POSTS_DIR):
        if fname.endswith(".md"):
            os.remove(os.path.join(POSTS_DIR, fname))


def git_commit_and_push(date_str: str) -> None:
    """Stage all changes and commit + push if there are changes."""
    subprocess.run(["git", "add", POSTS_DIR, INDEX_PATH], check=True)
    result = subprocess.run(["git", "diff", "--cached", "--quiet"])
    if result.returncode == 0:
        print("No changes detected — skipping commit.")
        return
    msg = f"chore: update bookmarks {date_str}"
    subprocess.run(["git", "commit", "-m", msg], check=True)
    subprocess.run(["git", "push"], check=True)
    print(f"Committed and pushed: {msg}")


def main() -> None:
    token = os.environ.get("RAINDROP_TOKEN")
    if not token:
        print("ERROR: RAINDROP_TOKEN environment variable not set", file=sys.stderr)
        sys.exit(1)

    print("Fetching bookmarks from Raindrop API...")
    raw_items = fetch_bookmarks(token)
    print(f"Fetched {len(raw_items)} bookmarks.")

    existing_slugs: set = set()
    bookmarks = [parse_bookmark(item, existing_slugs) for item in raw_items]
    bookmarks.sort(key=lambda b: b["date"], reverse=True)

    os.makedirs(POSTS_DIR, exist_ok=True)
    delete_existing_posts()

    for bm in bookmarks:
        write_bookmark_page(bm)

    changed = write_index(bookmarks)
    if not changed:
        print("Index unchanged.")

    today = datetime.now().strftime("%Y-%m-%d")
    git_commit_and_push(today)


if __name__ == "__main__":
    main()
