"""Product catalog generator and cache for Isvaryam.

Builds and caches a compact, stably sorted product catalog string
refreshed every 5 minutes. Keeping this catalog representation compact and
deterministically ordered maximizes Groq prompt caching efficiency and stays
well under tokens-per-minute limits.
"""

import json
import logging
import os
import time
from typing import Dict, List, Optional
from db import list_all_products

logger = logging.getLogger("isvaryam.catalog")

CACHE_TTL_SECONDS = 300  # 5 minutes
_cached_catalog_text: Optional[str] = None
_last_refresh_time: float = 0.0

INGREDIENTS_FILE = os.path.join(os.path.dirname(__file__), "ingredients.json")


def load_ingredients() -> Dict[str, List[str]]:
    """Load ingredients and health characteristics from static JSON."""
    try:
        if os.path.exists(INGREDIENTS_FILE):
            with open(INGREDIENTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as exc:
        logger.error("Failed to load ingredients.json: %s", exc)
    return {}


def format_product_line(prod: dict, ingredients_map: Dict[str, List[str]]) -> str:
    """Format a single product into a concise single-line representation."""
    name = prod.get("name", "Product")
    lower_name = name.lower()

    # Match ingredients
    highlights: List[str] = []
    for k, v in ingredients_map.items():
        if k in lower_name:
            highlights = v
            break

    # Quantities & Prices
    quantities = prod.get("quantities", [])
    if quantities:
        price_strs = [f"{q.get('size')}: ₹{q.get('price')}" for q in quantities if q.get("size")]
        prices_summary = ", ".join(price_strs)
    else:
        prices_summary = "Pricing available on request"

    hl_summary = f" ({', '.join(highlights)})" if highlights else ""
    return f"- {name}: {prices_summary}{hl_summary}"


def build_catalog_text() -> str:
    """Construct a compact, alphabetically sorted catalog string."""
    ingredients_map = load_ingredients()
    products = list_all_products()

    # Sort products deterministically by name for stable prompt caching
    sorted_products = sorted(products, key=lambda p: p.get("name", "").lower())

    lines = [
        "ISVARYAM PRODUCT CATALOG (Cold-Pressed & Natural):",
    ]
    for p in sorted_products:
        lines.append(format_product_line(p, ingredients_map))

    return "\n".join(lines)


def get_cached_catalog(force: bool = False) -> str:
    """Return the cached catalog string, refreshing every 5 minutes."""
    global _cached_catalog_text, _last_refresh_time
    now = time.time()

    if not force and _cached_catalog_text and (now - _last_refresh_time < CACHE_TTL_SECONDS):
        return _cached_catalog_text

    try:
        new_catalog = build_catalog_text()
        _cached_catalog_text = new_catalog
        _last_refresh_time = now
        return _cached_catalog_text
    except Exception as exc:
        logger.error("Failed to refresh catalog cache: %s", exc)
        if _cached_catalog_text:
            return _cached_catalog_text
        # Fallback minimal catalog
        return (
            "ISVARYAM PRODUCT CATALOG (Cold-Pressed & Natural):\n"
            "- Cold-Pressed Groundnut Oil: 500ml: ₹160, 1L: ₹310, 5L: ₹1500\n"
            "- Cold-Pressed Coconut Oil: 500ml: ₹185, 1L: ₹360\n"
            "- Wood-Pressed Sesame Oil (Gingelly/Chekku): 500ml: ₹220, 1L: ₹430\n"
            "- Pure Desi Cow Ghee (Bilona Method): 250ml: ₹350, 500ml: ₹680\n"
            "- Organic Jaggery Powder (Naatu Sakkarai): 500g: ₹65, 1kg: ₹120\n"
            "- Super Pack Combo (3x1L Oils): 3 x 1L Pack: ₹1050"
        )

