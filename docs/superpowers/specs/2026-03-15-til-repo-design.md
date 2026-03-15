# TIL Repository Design

**Date:** 2026-03-15
**Status:** Approved

---

## Overview

A personal, public "Today I Learned" (TIL) repository hosted on GitHub. Entries are short markdown write-ups on things learned across broader tech topics (software, hardware, networking, security, AI/ML, etc.). The site is automatically built and deployed to GitHub Pages using MkDocs Material on every push to `main`.

Not intended for wide community use — this is a personal knowledge log that happens to be public.

---

## Goals

- Capture short, focused learnings quickly without friction
- Organise by topic category with free-form growth
- Provide full-text search and tag-based browsing via a hosted static site
- Zero manual deployment — push markdown, site updates automatically

---

## Repository Structure

```
til/
├── docs/
│   ├── index.md               # Home page
│   ├── networking/
│   ├── security/
│   ├── ai-ml/
│   ├── hardware/
│   └── <category>/            # Add freely as needed
├── .github/
│   └── workflows/
│       └── deploy.yml
├── mkdocs.yml
└── README.md
```

- `docs/` contains all TIL entries organised by category folder
- Categories are plain directories — create a new folder to create a new category
- No fixed category list enforced; grows organically

---

## Entry Format

Each entry is a `.md` file with optional YAML frontmatter for date and tags.

**Filename convention:** `lowercase-hyphenated-description-of-the-learning.md`

**Template:**

```markdown
---
date: YYYY-MM-DD
tags:
  - tag-one
  - tag-two
---

# What You Learned — Stated As A Fact

One or two sentences of context: what led you here and why it matters.

## How It Works

The core explanation — prose, code snippets, diagrams, whatever best
communicates the learning.

## References

- [Source or doc that helped](https://example.com)
```

**Rules:**
- Title should be a factual statement of the learning, not a vague label
- Frontmatter is optional but encouraged (date and tags)
- Tags: lowercase, hyphenated, reused consistently (e.g., `ai-ml` not `AI/ML`)
- Target length: 50–300 words
- References section is optional but encouraged

---

## MkDocs Configuration

**`mkdocs.yml`:**

```yaml
site_name: TIL
site_description: Things I Learned
site_url: https://<github-username>.github.io/til/

theme:
  name: material
  features:
    - navigation.indexes
    - search.suggest
    - search.highlight

plugins:
  - search
  - tags
  - meta
```

- `search` — built-in full-text search (lunr.js), available via the search bar on the site
- `tags` — auto-generates a `/tags/` index page; every tag in frontmatter becomes a browsable page
- `meta` — reads frontmatter `date` field and displays it on each entry page
- Navigation is auto-discovered from `docs/` folder structure

---

## GitHub Actions — Deploy Workflow

**`.github/workflows/deploy.yml`:**

```yaml
name: Deploy to GitHub Pages
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: 3.x
      - run: pip install mkdocs-material
      - run: mkdocs gh-deploy --force
```

- Triggers on every push to `main`
- Installs MkDocs Material and deploys to the `gh-pages` branch
- GitHub Pages serves from `gh-pages` automatically
- No secrets or tokens required (uses `GITHUB_TOKEN` implicitly)

---

## GitHub Pages Setup

After the first workflow run:
1. Go to repo **Settings → Pages**
2. Set source to **Deploy from branch → `gh-pages` / `root`**
3. Site will be live at `https://<username>.github.io/til/`

**Custom domain (future):** Add a `CNAME` file to `docs/` containing the custom domain, update `site_url` in `mkdocs.yml`, and configure DNS. MkDocs will include the `CNAME` in the built output automatically.

---

## README

`README.md` at repo root is a simple pointer:

```markdown
# TIL

Things I Learned — a personal knowledge log.

Browse at: https://<username>.github.io/til/
```

---

## Out of Scope

- Community contributions / pull request workflow
- Comments or discussion system
- RSS feed (can be added later via MkDocs plugins)
- Full Datasette/SQLite search layer
- Automated entry creation scripts
