"""
tests/test_tools.py

Isolation tests for the three FitFindr tools. Run with:

    pytest tests/

search_listings is pure Python and fully deterministic, so it is tested
exhaustively here. suggest_outfit and create_fit_card call the Groq LLM, so
their tests cover only the deterministic failure modes (empty wardrobe,
empty outfit) that must not require a network call.
"""

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_empty_wardrobe


# ── search_listings ────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    # No designer ballgowns in the dataset, and nothing in XXS under $5.
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []  # empty list, no exception


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter_case_insensitive():
    # "m" should match sizes like "M", "S/M", "M/L" regardless of case.
    results = search_listings("vintage", size="m", max_price=None)
    assert len(results) > 0
    assert all("m" in item["size"].lower() for item in results)


def test_search_sorted_by_relevance():
    # The top result for a graphic-tee query should be a tagged graphic tee.
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    top = results[0]
    assert "graphic tee" in top["style_tags"] or "graphic" in top["style_tags"]


def test_search_excludes_zero_score():
    # A nonsense query matches no fields, so nothing should come back even
    # though the price ceiling alone would admit many listings.
    results = search_listings("xyzzy", size=None, max_price=100)
    assert results == []


# ── suggest_outfit (deterministic failure mode only) ───────────────────────

def test_suggest_outfit_empty_wardrobe_returns_string():
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = suggest_outfit(item, get_empty_wardrobe())
    assert isinstance(result, str)
    assert result.strip() != ""


# ── create_fit_card (deterministic failure mode only) ──────────────────────

def test_create_fit_card_empty_outfit_returns_error_string():
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = create_fit_card("", item)
    assert isinstance(result, str)
    assert result.strip() != ""  # descriptive error string, not an exception
