# Blog Section Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a blog section, About Me home page, and navigation tabs to the existing MkDocs Material TIL site.

**Architecture:** TIL category folders move into a `docs/til/` subfolder to enable clean top-level tab navigation. A blog section is added using MkDocs Material's built-in blog plugin at `docs/blog/`. The home page becomes a static About Me. An explicit `nav:` block in `mkdocs.yml` controls tab order (Home → TIL → Blog → Tags). Dark mode and social links are added to the theme config.

**Tech Stack:** MkDocs Material (blog plugin, navigation.tabs), GitHub Actions (existing deploy workflow), GitHub Pages

**Spec:** `docs/superpowers/specs/2026-03-15-blog-section-design.md`

---

## Chunk 1: Content Migration

### Task 1: Move TIL category folders into docs/til/

**Files:**
- Move: `docs/networking/` → `docs/til/networking/`
- Move: `docs/security/` → `docs/til/security/`
- Move: `docs/ai-ml/` → `docs/til/ai-ml/`
- Move: `docs/hardware/` → `docs/til/hardware/`

Use `git mv` so git tracks the moves as renames, preserving history.

- [ ] **Step 1: Create the docs/til/ parent directory**

```bash
mkdir docs/til
```

- [ ] **Step 2: Move category folders using git mv**

```bash
git mv docs/networking docs/til/networking
git mv docs/security docs/til/security
git mv docs/ai-ml docs/til/ai-ml
git mv docs/hardware docs/til/hardware
```

- [ ] **Step 3: Verify the moves**

```bash
git status
```

Expected output (staged renames):
```
Changes to be committed:
  renamed: docs/networking/.gitkeep -> docs/til/networking/.gitkeep
  renamed: docs/security/.gitkeep -> docs/til/security/.gitkeep
  renamed: docs/ai-ml/.gitkeep -> docs/til/ai-ml/.gitkeep
  renamed: docs/hardware/.gitkeep -> docs/til/hardware/.gitkeep
  renamed: docs/networking/dns-ttl-controls-how-long-resolvers-cache-records.md -> docs/til/networking/dns-ttl-controls-how-long-resolvers-cache-records.md
```

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor: move TIL categories into docs/til/"
```

- [ ] **Step 5: Verify commit succeeded**

```bash
git log --oneline -1
git status
```

Expected: latest commit shows the refactor message, working tree is clean.

---

### Task 2: Create docs/til/index.md (TIL landing page)

**Files:**
- Create: `docs/til/index.md`

- [ ] **Step 1: Create docs/til/index.md**

```markdown
# TIL

Short notes on things I've learned across software, hardware,
networking, security, AI/ML, and more.

Browse by category using the navigation, or search for a topic.
Use the [Tags](../tags.md) index to browse by tag.
```

- [ ] **Step 2: Commit**

```bash
git add docs/til/index.md
git commit -m "docs: add TIL section landing page"
```

---

### Task 3: Rewrite docs/index.md as About Me

**Files:**
- Modify: `docs/index.md`

- [ ] **Step 1: Replace docs/index.md with your About Me content**

This is personal content — write your own bio. The structure below is a template:

```markdown
# Mark Gravestock

[Write a short bio here — who you are, what you work on, what you're interested in.
One or two sentences is fine.]

## Links

- [GitHub](https://github.com/MarkGravestock)
- [LinkedIn](https://linkedin.com/in/YOUR-LINKEDIN-SLUG)

## This Site

- [TIL](til/index.md) — short notes on things I've learned
- [Blog](blog/index.md) — longer posts
```

**Finding your LinkedIn slug:** Go to your LinkedIn profile. The slug is the final segment of the URL — e.g. `linkedin.com/in/markgravestock` → slug is `markgravestock`.

- [ ] **Step 2: Commit**

```bash
git add docs/index.md
git commit -m "docs: rewrite home page as About Me"
```

---

### Task 4: Create blog directory structure

**Files:**
- Create: `docs/blog/posts/.gitkeep`

The blog plugin auto-generates `docs/blog/index.md` at build time — do NOT create it manually.

- [ ] **Step 1: Create blog/posts/ directory with a gitkeep**

In Git Bash (recommended on Windows):
```bash
mkdir -p docs/blog/posts
touch docs/blog/posts/.gitkeep
```

In PowerShell (if not using Git Bash):
```powershell
New-Item -ItemType Directory -Force docs\blog\posts
New-Item -ItemType File -Force docs\blog\posts\.gitkeep
```

- [ ] **Step 2: Commit**

```bash
git add docs/blog/posts/.gitkeep
git commit -m "chore: add blog/posts directory"
```

---

## Chunk 2: Configuration Update

### Task 5: Update mkdocs.yml

**Files:**
- Modify: `mkdocs.yml`

- [ ] **Step 1: Replace mkdocs.yml with updated config**

```yaml
site_name: Things I Learned
site_description: A personal knowledge log
site_url: https://markgravestock.github.io/things-i-learned/

theme:
  name: material
  palette:
    scheme: slate
  features:
    - navigation.tabs
    - navigation.indexes
    - search.suggest
    - search.highlight

plugins:
  - search
  - tags
  - meta
  - blog:
      blog_dir: blog

nav:
  - Home: index.md
  - TIL:
      - til/index.md
      - Networking: til/networking/dns-ttl-controls-how-long-resolvers-cache-records.md
  - Blog: blog/index.md
  - Tags: tags.md

extra:
  social:
    - icon: fontawesome/brands/github
      link: https://github.com/MarkGravestock
    - icon: fontawesome/brands/linkedin
      link: https://linkedin.com/in/<your-linkedin-slug>  # replace with your LinkedIn slug

exclude_docs: |
  superpowers/
```

> Replace `<your-linkedin-slug>` with the path segment from your LinkedIn profile URL (e.g. `markgravestock`).

- [ ] **Step 2: Commit**

```bash
git add mkdocs.yml
git commit -m "feat: add blog plugin, navigation tabs, dark mode, and social links"
```

---

### Task 6: Push and verify deployment

- [ ] **Step 1: Push to GitHub**

```bash
git push
```

- [ ] **Step 2: Verify GitHub Actions workflow passes**

Go to: `https://github.com/MarkGravestock/things-i-learned/actions`

Wait for the "Deploy to GitHub Pages" workflow to complete. All steps should show green.

If the build fails, check the workflow logs for the failing step. Common issues:
- `nav:` references a file that doesn't exist → check the path matches exactly
- Blog plugin conflict → ensure `docs/blog/index.md` does not exist in the repo

- [ ] **Step 3: Verify the live site**

Open: `https://markgravestock.github.io/things-i-learned/`

Check:
- Header shows tabs: Home | TIL | Blog | Tags
- Home tab shows the About Me page
- TIL tab shows the TIL landing page with Networking category in the sidebar
- Blog tab shows an empty blog listing (no posts yet — that's fine)
- Tags tab shows the tags index
- Site is in dark mode (slate theme)
- Footer shows GitHub and LinkedIn icons (LinkedIn links to your profile once slug is updated)

---

## Reference: Adding Your First Blog Post

Once the site is live, create a post:

1. Create `docs/blog/posts/YYYY-MM-DD-slug.md`:

```markdown
---
date: 2026-03-15
tags:
  - general
categories:
  - general
---

# Your Post Title

<!-- more -->

Post content here...
```

2. Commit and push:

```bash
git add docs/blog/posts/
git commit -m "blog: your post title"
git push
```

The post appears automatically in the Blog listing — no nav changes needed for blog posts.

---

## Reference: Adding a New TIL Category

When you create your first entry in a new category:

1. Create `docs/til/<category>/your-entry.md`
2. Add a nav entry to `mkdocs.yml` under the TIL section:

```yaml
- TIL:
    - til/index.md
    - Networking: til/networking/dns-ttl-controls-how-long-resolvers-cache-records.md
    - New Category: til/new-category/your-entry.md  # ← add this
```

3. As the category grows, you can expand the nav entry to list multiple files or use a section:

```yaml
- New Category:
    - til/new-category/entry-one.md
    - til/new-category/entry-two.md
```
