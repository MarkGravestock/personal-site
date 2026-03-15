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
