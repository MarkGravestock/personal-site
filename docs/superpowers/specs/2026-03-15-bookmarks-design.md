# Bookmarks Section Design

**Date:** 2026-03-15
**Status:** Approved

## Overview

Port the existing Raindrop.io bookmarks integration from `MarkGravestock.github.io` (Jekyll) into the `personal-site` MkDocs Material site. Each bookmark becomes its own MkDocs page with frontmatter tags wired into the shared MkDocs tags index. A generated index page provides a monthly card-grid listing.

## Goals

- Bookmarks appear as a top-level navigation tab alongside TIL and Blog
- Each bookmark has its own page with MkDocs `tags:` frontmatter, fully integrated with the existing tags plugin
- Bookmark listing uses MkDocs Material card grid — no custom CSS required
- GitHub Actions workflow consolidates into `personal-site`, running on the same schedule (daily 08:00 UTC)
- Deleted bookmarks in Raindrop are automatically removed from the site on the next run

## Architecture

### File Structure

```
personal-site/
├── docs/
│   └── bookmarks/
│       ├── index.md                              # generated listing (card grid, by month)
│       └── posts/
│           ├── .gitkeep                          # ensures directory exists in repo
│           ├── 2026-03-10-some-title.md          # one page per bookmark
│           └── ...
├── _scripts/
│   └── update_bookmarks.py                       # updated generation script
└── .github/
    └── workflows/
        └── update-bookmarks.yml                  # moved from old repo
```

### Data Flow

1. GitHub Actions triggers the Python script daily at 08:00 UTC
2. Script fetches all pages from the Raindrop API into memory — aborts without commit if any page fails
3. Script deletes all existing `docs/bookmarks/posts/*.md` files (excluding `.gitkeep`)
4. Script writes one `.md` file per bookmark to `docs/bookmarks/posts/`
5. Script writes generated `docs/bookmarks/index.md` (monthly card-grid listing)
6. Script commits and pushes only if content has changed
7. Push triggers the existing `deploy.yml` which builds and deploys the site to GitHub Pages

## Section 2: Script Changes

### Prerequisites

- `docs/bookmarks/posts/.gitkeep` committed to repo (directory must exist before first run)
- `_scripts/` directory created and `update_bookmarks.py` committed
- Script uses only Python stdlib (`urllib.request`, `os`, `re`, `datetime`) — no pip install required

### Individual Bookmark Pages

Each bookmark is written to `docs/bookmarks/posts/<date>-<slug>.md`.

**Slug generation:** title lowercased, non-alphanumeric chars replaced with hyphens, consecutive hyphens collapsed, truncated to 50 chars, trailing hyphens stripped. On slug collision (same date, same truncated title), append the Raindrop bookmark ID suffix (e.g. `-a1b2c3`) to disambiguate.

Example: `"Some Cool Article!"` → `2026-03-10-some-cool-article.md`

**Script uses `os.makedirs("docs/bookmarks/posts", exist_ok=True)`** before writing to handle the case where the directory is absent.

**Page format:**
```markdown
---
title: "Some Cool Article"
date: 2026-03-10
tags:
  - python
  - web
---

**[Some Cool Article](https://example.com)**

example.com · 10 Mar 2026

> Optional note (omitted if no note)
```

Notes:
- No `layout:` or `categories:` keys — those are Jekyll artifacts
- Tags are the Raindrop user tags only; system tags (`article`, `link`, `public`, `video`, `image`, `document`, `audio`) are filtered out
- If a bookmark has no user tags, the `tags:` frontmatter key is omitted entirely
- The note blockquote is omitted if the bookmark has no note

### Generated Index Page

`docs/bookmarks/index.md` is fully regenerated on every run.

**Format:**
```markdown
---
title: Bookmarks
---
# Bookmarks

A collection of useful things I've found on the web.

## March 2026

<div class="grid cards" markdown>

- **[Some Cool Article](posts/2026-03-10-some-cool-article.md)**

    `#python` `#web` · example.com · 10 Mar

</div>

## February 2026

<div class="grid cards" markdown>
...
</div>
```

Notes:
- Months appear in reverse chronological order (newest first)
- Tags rendered as inline code spans (`` `#tag` ``) — no custom CSS needed
- If a bookmark has no tags, the tag span row is omitted from the card
- Empty months (all bookmarks deleted) are suppressed — no empty `<div class="grid cards">` blocks
- Links use `.md` extension (`posts/2026-03-10-slug.md`) — MkDocs resolves these to HTML at build time; this is intentional

### Change Detection and Error Handling

- **Fetch first:** All Raindrop API pages are fetched into memory before any file is deleted or written. If any page fetch fails (non-200 status, timeout, network error), the script exits non-zero and makes no changes — GHA marks the run as failed
- **Then delete:** Script deletes `docs/bookmarks/posts/*.md` (excluding `.gitkeep`) only after a successful full fetch
- **Then write:** Individual pages and index are written
- Script compares newly generated `index.md` content against the existing file; commits only if changed
- Commit message format: `chore: update bookmarks YYYY-MM-DD`

## Section 3: `mkdocs.yml` Changes

### Navigation

Add `Bookmarks` as a top-level tab, before Tags:

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

### Suppress Nav Warnings for Individual Bookmark Pages

Individual bookmark pages are built and accessible (via tags index and search) but not listed in `nav:`. Suppress the MkDocs "not in nav" warning:

```yaml
validation:
  nav:
    omitted_files: ignore
```

### Markdown Extensions (required for card grid)

The `<div class="grid cards" markdown>` syntax requires `attr_list` and `md_in_html` extensions:

```yaml
markdown_extensions:
  - attr_list
  - md_in_html
```

Add these to the existing `markdown_extensions` block (or create it if absent).

## Section 4: GitHub Actions Workflow

### `update-bookmarks.yml`

No `pip install` step required — script uses Python stdlib only.

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
      - name: Update bookmarks
        env:
          RAINDROP_TOKEN: ${{ secrets.RAINDROP_TOKEN }}
        run: python _scripts/update_bookmarks.py
```

The push from this workflow triggers the existing `deploy.yml`, which builds and deploys the full site. No changes to `deploy.yml` are needed.

### Secret Migration

`RAINDROP_TOKEN` must be added to `personal-site` repo secrets manually:
**GitHub → personal-site → Settings → Secrets and variables → Actions → New repository secret**

## Out of Scope

- Pagination on the bookmarks index page (all bookmarks on one page for now)
- Search/filter within the bookmarks page
- Categories (Raindrop collections) — single collection only
- Keeping the old Jekyll site's bookmarks page in sync
