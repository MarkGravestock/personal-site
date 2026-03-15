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
2. Script calls Raindrop API (collection ID: 64296840) with `RAINDROP_TOKEN` secret
3. Script deletes all existing `docs/bookmarks/posts/*.md` files
4. Script writes one `.md` file per bookmark to `docs/bookmarks/posts/`
5. Script writes generated `docs/bookmarks/index.md` (monthly card-grid listing)
6. Script commits and pushes only if content has changed
7. Existing deploy GHA (`deploy.yml`) builds and deploys the site to GitHub Pages

## Section 2: Script Changes

### Individual Bookmark Pages

Each bookmark is written to `docs/bookmarks/posts/<date>-<slug>.md`.

**Slug generation:** title lowercased, non-alphanumeric chars replaced with hyphens, consecutive hyphens collapsed, truncated to 50 chars, trailing hyphens stripped.

Example: `"Some Cool Article!"` → `2026-03-10-some-cool-article.md`

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
- Tags rendered as inline code spans (`` `#tag` ``) — visually consistent with MkDocs Material, no custom CSS needed
- If a bookmark has no tags, the tag span is omitted
- If a bookmark has no note, the blockquote is omitted from the individual page

### Change Detection

- Script deletes all `docs/bookmarks/posts/*.md` before regenerating (handles deleted bookmarks)
- Script compares newly generated `index.md` content against the existing file
- Only commits if the index content has changed (individual post changes are caught by git diff regardless)
- Commit message format: `chore: update bookmarks YYYY-MM-DD`

### Filtered Tags

System tags excluded from output (same as current implementation):
`article`, `link`, `public`, `video`, `image`, `document`, `audio`

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

### `not_in_nav`

Suppress MkDocs warnings for individual bookmark pages (discoverable via tags and search, not nav):

```yaml
not_in_nav: |
  bookmarks/posts/*
```

No new plugins required. The existing `tags` plugin picks up bookmark pages via their frontmatter automatically.

## Section 4: GitHub Actions Workflow

### `update-bookmarks.yml`

Copied from `MarkGravestock.github.io` with output path updated:

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

### Secret Migration

`RAINDROP_TOKEN` must be added to `personal-site` repo secrets manually:
**GitHub → personal-site → Settings → Secrets and variables → Actions → New repository secret**

## Out of Scope

- Pagination on the bookmarks index page (all bookmarks on one page for now)
- Search/filter within the bookmarks page
- Categories (Raindrop collections) — single collection only
- Keeping the old Jekyll site's bookmarks page in sync
