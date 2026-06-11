"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

# Model used by the LLM-backed tools (Groq free tier).
_MODEL = "llama-3.3-70b-versatile"

# Common words that carry no search signal — dropped before keyword scoring so
# a phrase like "looking for a vintage tee" scores on "vintage"/"tee" only.
_STOPWORDS = {
    "a", "an", "and", "the", "for", "with", "under", "in", "of", "to", "my",
    "i", "im", "looking", "want", "wanted", "need", "some", "something",
    "thats", "that", "this", "find", "me", "is", "are", "on", "or",
}


def _tokenize(text: str) -> list[str]:
    """Lowercase a string and split it into alphanumeric word tokens."""
    return re.findall(r"[a-z0-9]+", text.lower())


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    # 1. Filter by hard constraints (price ceiling, size) before scoring.
    candidates = []
    for item in listings:
        if max_price is not None and item["price"] > max_price:
            continue
        if size is not None and size.lower() not in item["size"].lower():
            continue
        candidates.append(item)

    # 2. Score each candidate by keyword overlap with the description.
    #    Matches in style_tags and title count more than the free-text body.
    query_tokens = [t for t in _tokenize(description) if t not in _STOPWORDS]

    scored = []
    for item in candidates:
        title_tokens = set(_tokenize(item["title"]))
        tag_tokens = set(_tokenize(" ".join(item["style_tags"])))
        desc_tokens = set(_tokenize(item["description"]))
        category_tokens = set(_tokenize(item["category"]))

        score = 0
        for token in query_tokens:
            if token in tag_tokens:
                score += 3
            if token in title_tokens:
                score += 2
            if token in category_tokens:
                score += 2
            if token in desc_tokens:
                score += 1

        # 3. Drop anything with no keyword relevance at all.
        if score > 0:
            scored.append((score, item))

    # 4. Sort by score (highest first); break ties by lower price.
    scored.sort(key=lambda pair: (-pair[0], pair[1]["price"]))

    # 5. Return just the listing dicts. Empty list if nothing matched.
    return [item for _, item in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    item_desc = (
        f"{new_item['title']} "
        f"(category: {new_item['category']}, "
        f"colors: {', '.join(new_item['colors'])}, "
        f"style: {', '.join(new_item['style_tags'])})"
    )

    items = wardrobe.get("items", [])

    if not items:
        # Empty-wardrobe branch: no pieces to name, so give general advice.
        prompt = (
            f"A user is considering buying this secondhand item:\n{item_desc}\n\n"
            "They haven't told us anything in their wardrobe yet. In 2-3 "
            "sentences, suggest what kinds of pieces would pair well with it, "
            "what vibe it suits, and one concrete styling tip. Be specific and "
            "practical — name types of garments and shoes, not brands."
        )
    else:
        # Format the wardrobe into a readable list for the prompt.
        wardrobe_lines = "\n".join(
            f"- {it['name']} ({it['category']}, {', '.join(it['colors'])})"
            for it in items
        )
        prompt = (
            f"A user found this secondhand item:\n{item_desc}\n\n"
            f"Here is their current wardrobe:\n{wardrobe_lines}\n\n"
            "Suggest 1-2 complete outfits that pair the new item with SPECIFIC "
            "pieces named from their wardrobe above. Reference the wardrobe items "
            "by name. Keep it to 2-4 sentences and add one concrete styling tip "
            "(how to tuck, cuff, layer, etc.)."
        )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a sharp, practical secondhand-fashion stylist.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        suggestion = response.choices[0].message.content.strip()
        if suggestion:
            return suggestion
        # Empty model output — fall through to the fallback below.
    except Exception as exc:  # network/API/auth failure — stay usable
        print(f"[suggest_outfit] LLM call failed: {exc}")

    # Fallback styling advice so the agent (and create_fit_card) can continue.
    return (
        f"Style the {new_item['title']} as the statement piece and keep the "
        f"rest simple — pair it with well-fitting basics in neutral tones and "
        f"shoes that match its {', '.join(new_item['style_tags'][:2])} vibe."
    )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # 1. Guard against an empty or whitespace-only outfit string.
    if not outfit or not outfit.strip():
        return (
            "Can't write a fit card yet — no outfit suggestion was provided. "
            "Run suggest_outfit first to get a look to caption."
        )

    title = new_item["title"]
    price = new_item["price"]
    platform = new_item["platform"]

    # 2. Build a prompt with the item details and the styled outfit.
    prompt = (
        f"Write a short, shareable social-media caption (an OOTD / thrift-haul "
        f"post) for this secondhand find.\n\n"
        f"Item: {title}\n"
        f"Price: ${price:.0f}\n"
        f"Platform: {platform}\n"
        f"How it's styled: {outfit}\n\n"
        "Rules:\n"
        "- 2-4 sentences, casual and first-person, like a real post (NOT a "
        "product description).\n"
        f"- Mention the item, the ${price:.0f} price, and {platform} naturally, "
        "once each.\n"
        "- Capture the outfit's vibe in specific terms. An emoji or two is fine.\n"
        "- Return only the caption text, nothing else."
    )

    # 3. Call the LLM at a higher temperature so captions vary run-to-run.
    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You write fun, authentic-sounding outfit captions for thrift finds.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=1.0,
        )
        caption = response.choices[0].message.content.strip()
        if caption:
            return caption
    except Exception as exc:  # network/API/auth failure — stay usable
        print(f"[create_fit_card] LLM call failed: {exc}")

    # Fallback caption built from the item fields if the LLM is unavailable.
    return (
        f"thrifted this {title} off {platform} for ${price:.0f} and i'm obsessed — "
        f"styled it exactly how i wanted. full fit in my stories ✨"
    )
