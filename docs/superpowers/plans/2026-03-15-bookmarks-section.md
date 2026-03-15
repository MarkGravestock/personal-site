# Bookmarks Section Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the Raindrop.io bookmarks integration into the `personal-site` MkDocs Material site, with one page per bookmark wired into the MkDocs tags index.

**Architecture:** A Python script fetches all bookmarks from the Raindrop API, writes one `.md` file per bookmark into `docs/bookmarks/posts/`, and regenerates `docs/bookmarks/index.md` as a monthly card-grid listing. MkDocs tags plugin picks up each bookmark's frontmatter tags automatically. A daily GitHub Actions workflow runs the script and pushes changes, which then triggers the existing deploy workflow.

**Tech Stack:** Python 3.12 (stdlib only — `urllib.request`, `os`, `re`, `datetime`, `json`), MkDocs Material (card grid via `attr_list` + `md_in_html` extensions), GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-03-15-bookmarks-design.md`

---

## Chunk 1: Setup and mkdocs.yml

### Task 1: Create directory structure

**Files:**
- Create: `docs/bookmarks/posts/.gitkeep`
- Create: `_scripts/.gitkeep` (placeholder until script is added)

- [ ] **Step 1: Create the directories and gitkeep files**

```bash
mkdir -p docs/bookmarks/posts
touch docs/bookmarks/posts/.gitkeep
mkdir -p _scripts
touch _scripts/.gitkeep
```

- [ ] **Step 2: Commit**

```bash
git add docs/bookmarks/posts/.gitkeep _scripts/.gitkeep
git commit -m "chore: add bookmarks/posts and _scripts directories"
```

---

### Task 2: Update `mkdocs.yml`

**Files:**
- Modify: `mkdocs.yml`

Current `mkdocs.yml` has no `markdown_extensions` block. We need to add `attr_list` and `md_in_html` (required for card grids), a `validation` block (to suppress nav warnings for individual bookmark pages), and `Bookmarks` in the nav.

- [ ] **Step 1: Add markdown extensions, validation block, and Bookmarks nav entry**

Open `mkdocs.yml` and apply these changes:

Add after the `plugins:` block:

```yaml
markdown_extensions:
  - attr_list
  - md_in_html
```

Add a `validation:` block (new top-level key):

```yaml
validation:
  nav:
    omitted_files: ignore
```

Update the `nav:` block to add Bookmarks before Tags:

```yaml
nav:
  - Home: index.md
  - TIL:
      - til/index.md
      - Networking: til/networking/dns-ttl-controls-how-long-resolvers-cache-records.md
  - Blog: blog/index.md
  - Bookmarks: bookmarks/index.md
  - Tags: tags.md
```

- [ ] **Step 2: Create a placeholder `docs/bookmarks/index.md`** so MkDocs can build without errors (the script will overwrite this later):

```bash
cat > docs/bookmarks/index.md << 'EOF'
---
title: Bookmarks
---
# Bookmarks

A collection of useful things I've found on the web.
EOF
```

- [ ] **Step 3: Verify MkDocs builds locally**

```bash
pip install -r requirements.txt
mkdocs build --strict
```

Expected: build succeeds with no errors. The Bookmarks tab appears in the nav. Ignore any warning about `bookmarks/posts/` being empty.

- [ ] **Step 4: Commit**

```bash
git add mkdocs.yml docs/bookmarks/index.md
git commit -m "feat: add bookmarks nav, markdown extensions, and validation config"
```

---

## Chunk 2: Python Script (TDD)

The script has two layers:
1. **Pure functions** — slug generation, tag filtering, page rendering — easily testable
2. **I/O layer** — API fetch, file write, git commit — tested via a manual smoke test at the end

### Task 3: Write failing tests for pure functions

**Files:**
- Create: `_scripts/test_update_bookmarks.py`

Install pytest for local testing (not added to `requirements.txt` — only needed for development):

```bash
pip install pytest
```

- [ ] **Step 1: Create the test file**

Create `_scripts/test_update_bookmarks.py`:

```python
"""Tests for pure functions in update_bookmarks.py"""
import pytest
from update_bookmarks import (
    generate_slug,
    filter_tags,
    render_bookmark_page,
    render_card,
    render_index,
)

# ---------------------------------------------------------------------------
# generate_slug
# ---------------------------------------------------------------------------

def test_generate_slug_basic():
    assert generate_slug("Some Cool Article", "2026-03-10", set()) == "2026-03-10-some-cool-article"

def test_generate_slug_strips_special_chars():
    assert generate_slug("Some Cool Article!", "2026-03-10", set()) == "2026-03-10-some-cool-article"

def test_generate_slug_collapses_hyphens():
    assert generate_slug("A  B---C", "2026-03-10", set()) == "2026-03-10-a-b-c"

def test_generate_slug_truncates_at_50_chars():
    long_title = "A" * 60
    slug = generate_slug(long_title, "2026-03-10", set())
    # date prefix is 11 chars + hyphen = 12, slug body should be <= 50
    assert len(slug) <= 62  # 11 (date) + 1 (-) + 50 (body)

def test_generate_slug_collision_appends_id():
    existing = {"2026-03-10-my-title"}
    slug = generate_slug("My Title", "2026-03-10", existing, bookmark_id="abc123")
    assert slug == "2026-03-10-my-title-abc123"

def test_generate_slug_no_trailing_hyphens():
    slug = generate_slug("Hello---", "2026-03-10", set())
    assert not slug.endswith("-")

# ---------------------------------------------------------------------------
# filter_tags
# ---------------------------------------------------------------------------

SYSTEM_TAGS = {"article", "link", "public", "video", "image", "document", "audio"}

def test_filter_tags_removes_system_tags():
    tags = ["python", "article", "web", "link"]
    assert filter_tags(tags) == ["python", "web"]

def test_filter_tags_empty_input():
    assert filter_tags([]) == []

def test_filter_tags_all_system():
    assert filter_tags(["article", "link", "public"]) == []

def test_filter_tags_preserves_order():
    tags = ["zebra", "apple", "mango"]
    assert filter_tags(tags) == ["zebra", "apple", "mango"]

# ---------------------------------------------------------------------------
# render_bookmark_page
# ---------------------------------------------------------------------------

def make_bookmark(**kwargs):
    defaults = {
        "title": "Test Bookmark",
        "link": "https://example.com",
        "domain": "example.com",
        "tags": ["python", "web"],
        "note": "",
        "date": "2026-03-10",
        "date_display": "10 Mar 2026",
        "slug": "2026-03-10-test-bookmark",
        "raindrop_id": "abc123",
    }
    defaults.update(kwargs)
    return defaults

def test_render_bookmark_page_basic():
    bm = make_bookmark()
    page = render_bookmark_page(bm)
    assert "title: \"Test Bookmark\"" in page
    assert "date: 2026-03-10" in page
    assert "- python" in page
    assert "- web" in page
    assert "[Test Bookmark](https://example.com)" in page
    assert "example.com · 10 Mar 2026" in page

def test_render_bookmark_page_no_tags_omits_tags_key():
    bm = make_bookmark(tags=[])
    page = render_bookmark_page(bm)
    assert "tags:" not in page

def test_render_bookmark_page_with_note():
    bm = make_bookmark(note="Very useful resource")
    page = render_bookmark_page(bm)
    assert "> Very useful resource" in page

def test_render_bookmark_page_without_note():
    bm = make_bookmark(note="")
    page = render_bookmark_page(bm)
    assert "> " not in page

def test_render_bookmark_page_title_with_quotes_escaped():
    bm = make_bookmark(title='He said "hello"')
    page = render_bookmark_page(bm)
    # Title in frontmatter should not break YAML
    assert 'title: "He said \\"hello\\""' in page or "title: 'He said \"hello\"'" in page

# ---------------------------------------------------------------------------
# render_card
# ---------------------------------------------------------------------------

def test_render_card_basic():
    bm = make_bookmark()
    card = render_card(bm)
    assert "**[Test Bookmark](posts/2026-03-10-test-bookmark.md)**" in card
    assert "`#python`" in card
    assert "`#web`" in card
    assert "example.com" in card
    assert "10 Mar" in card

def test_render_card_no_tags_omits_tag_line():
    bm = make_bookmark(tags=[])
    card = render_card(bm)
    assert "`#" not in card

# ---------------------------------------------------------------------------
# render_index
# ---------------------------------------------------------------------------

def test_render_index_groups_by_month():
    bookmarks = [
        make_bookmark(title="A", date="2026-03-10", date_display="10 Mar 2026", slug="2026-03-10-a"),
        make_bookmark(title="B", date="2026-02-05", date_display="5 Feb 2026", slug="2026-02-05-b"),
    ]
    index = render_index(bookmarks)
    assert "## March 2026" in index
    assert "## February 2026" in index
    # March comes before February (reverse chronological)
    assert index.index("## March 2026") < index.index("## February 2026")

def test_render_index_empty_months_suppressed():
    """No empty <div class='grid cards'> blocks."""
    bookmarks = [
        make_bookmark(title="A", date="2026-03-10", date_display="10 Mar 2026", slug="2026-03-10-a"),
    ]
    index = render_index(bookmarks)
    # Only one month section
    assert index.count("## ") == 1

def test_render_index_has_card_grid_wrapper():
    bookmarks = [make_bookmark()]
    index = render_index(bookmarks)
    assert '<div class="grid cards" markdown>' in index
    assert "</div>" in index

def test_render_index_has_frontmatter():
    index = render_index([])
    assert "---\ntitle: Bookmarks\n---" in index
```

- [ ] **Step 2: Run tests — expect ImportError (module doesn't exist yet)**

```bash
cd _scripts
pytest test_update_bookmarks.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'update_bookmarks'` — confirms tests are wired up correctly.

---

### Task 4: Implement pure functions (make tests pass)

**Files:**
- Create: `_scripts/update_bookmarks.py`

- [ ] **Step 1: Create `_scripts/update_bookmarks.py` with pure functions**

```python
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

def filter_tags(tags: list[str]) -> list[str]:
    """Remove Raindrop system tags, keep user tags."""
    return [t for t in tags if t.lower() not in SYSTEM_TAGS]


def generate_slug(title: str, date: str, existing_slugs: set, bookmark_id: str = "") -> str:
    """
    Generate a filename-safe slug: '<date>-<title-slug>'.
    On collision with existing_slugs, appends '-<bookmark_id>'.
    """
    # Slugify title
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
    """'2026-03-10' → '10 Mar 2026'"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%-d %b %Y")  # Linux; Windows needs %#d
    except ValueError:
        return date_str


def _format_month_heading(date_str: str) -> str:
    """'2026-03-10' → 'March 2026'"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%B %Y")
    except ValueError:
        return date_str


def _month_key(date_str: str) -> str:
    """'2026-03-10' → '2026-03' (for grouping and sorting)"""
    return date_str[:7]


def render_bookmark_page(bm: dict) -> str:
    """Render the full Markdown content for a single bookmark page."""
    lines = ["---"]
    # Escape double quotes in title for YAML
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
    lines.append(f'{bm["domain"]} · {bm["date_display"]}')

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
    date_short = datetime.strptime(bm["date"], "%Y-%m-%d").strftime("%-d %b")

    card_lines = [f"- **[{title}](posts/{slug}.md)**", ""]

    meta_parts = []
    if tags:
        tag_str = " ".join(f"`#{t}`" for t in tags)
        meta_parts.append(tag_str)
    meta_parts.append(f"{domain} · {date_short}")

    card_lines.append(f"    {' · '.join(meta_parts) if not tags else tag_str + ' · ' + domain + ' · ' + date_short}")
    card_lines.append("")
    return "\n".join(card_lines)


def render_index(bookmarks: list[dict]) -> str:
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

    # Group by month, reverse chronological
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

def fetch_bookmarks(token: str) -> list[dict]:
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

    # Date display: try Linux format, fall back to zero-padded
    try:
        date_display = datetime.strptime(date, "%Y-%m-%d").strftime("%-d %b %Y")
    except ValueError:
        date_display = datetime.strptime(date, "%Y-%m-%d").strftime("%d %b %Y").lstrip("0")

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


def write_index(bookmarks: list[dict]) -> bool:
    """
    Write docs/bookmarks/index.md. Returns True if content changed.
    """
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

    # Parse all bookmarks (fetch-first, then mutate filesystem)
    existing_slugs: set = set()
    bookmarks = [parse_bookmark(item, existing_slugs) for item in raw_items]
    # Sort newest first
    bookmarks.sort(key=lambda b: b["date"], reverse=True)

    # Now safe to delete and rewrite
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
```

- [ ] **Step 2: Run the tests**

```bash
cd _scripts
pytest test_update_bookmarks.py -v
```

Expected: most tests pass. Investigate and fix any failures before proceeding. Common issues:
- `%-d` strftime format (Linux only) — on Windows, replace with `%#d`; the `date_display` fallback in `parse_bookmark` handles this, but `render_card` and `_format_date_display` also use it — adjust if running tests on Windows.
- `render_card` meta line formatting — check the tag + domain + date assembly matches test expectations.

Fix any failures, re-run until all tests pass.

- [ ] **Step 3: Remove `_scripts/.gitkeep` (now that the real files exist) and commit**

```bash
rm _scripts/.gitkeep
git add _scripts/update_bookmarks.py _scripts/test_update_bookmarks.py
git commit -m "feat: add bookmarks update script with tests"
```

---

### Task 5: Smoke test the script locally

- [ ] **Step 1: Run the script locally with your Raindrop token**

```bash
cd <repo root>
RAINDROP_TOKEN=<your-token> python _scripts/update_bookmarks.py
```

Expected output:
```
Fetching bookmarks from Raindrop API...
Fetched N bookmarks.
Committed and pushed: chore: update bookmarks 2026-03-15
```

Check:
- `docs/bookmarks/posts/` contains `.md` files (one per bookmark)
- `docs/bookmarks/index.md` contains monthly card grid sections
- Individual pages have correct frontmatter with `tags:`

- [ ] **Step 2: Build MkDocs locally and verify**

```bash
mkdocs build --strict
```

Open `site/bookmarks/index.html` in a browser. Verify:
- Bookmarks tab appears in nav
- Card grid renders correctly
- Open `site/tags/index.html` — verify bookmark tags appear alongside TIL tags

- [ ] **Step 3: If the smoke test committed changes to the repo, verify git log looks clean**

```bash
git log --oneline -5
```

---

## Chunk 3: GitHub Actions Workflow

### Task 6: Add `update-bookmarks.yml` workflow

**Files:**
- Create: `.github/workflows/update-bookmarks.yml`

- [ ] **Step 1: Create the workflow file**

```yaml
name: Update Bookmarks

on:
  schedule:
    - cron: '0 8 * * *'
  workflow_dispatch:

jobs:
  update:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Configure git identity
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
      - name: Update bookmarks
        env:
          RAINDROP_TOKEN: ${{ secrets.RAINDROP_TOKEN }}
        run: python _scripts/update_bookmarks.py
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/update-bookmarks.yml
git commit -m "feat: add update-bookmarks GitHub Actions workflow"
git push origin main
```

---

### Task 7: Add `RAINDROP_TOKEN` secret and verify

⚠️ **Manual step — cannot be automated.**

- [ ] **Step 1: Add the secret to `personal-site`**

GitHub → personal-site → Settings → Secrets and variables → Actions → **New repository secret**

- Name: `RAINDROP_TOKEN`
- Value: your Raindrop API token (same value used in the smoke test above)

- [ ] **Step 2: Trigger the workflow manually**

GitHub → personal-site → Actions → Update Bookmarks → **Run workflow**

- [ ] **Step 3: Verify the workflow run succeeds**

Watch the Actions log. Expected:
- Python script runs, fetches bookmarks, commits and pushes (or reports "No changes detected")
- The push triggers `deploy.yml`, which builds and deploys the site

- [ ] **Step 4: Check the live site**

Visit `https://markgravestock.github.io/personal-site/bookmarks/` and verify:
- Bookmarks appear in a card grid grouped by month
- Tags are clickable and appear in `https://markgravestock.github.io/personal-site/tags/`
- Individual bookmark pages (linked from cards) render correctly with tags in their sidebar
