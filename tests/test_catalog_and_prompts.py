"""Unit tests for catalog caching, TTL refresh, stale-cache fallback, and prompt templates."""

import time
from unittest.mock import patch
import catalog
from catalog import build_catalog_text, get_cached_catalog
from prompts import SYSTEM_PROMPT, get_system_prompt


def test_catalog_is_stably_ordered():
    """Ensure catalog lines are sorted alphabetically for stable prompt caching."""
    catalog_text = build_catalog_text()
    lines = [line for line in catalog_text.split("\n") if line.startswith("- ")]
    product_names = [line.split(":")[0].replace("- ", "").strip().lower() for line in lines]
    assert product_names == sorted(product_names)


def test_cached_catalog_reuse():
    """Test cache returns identical string on repeated calls within TTL."""
    cat1 = get_cached_catalog()
    cat2 = get_cached_catalog()
    assert cat1 == cat2
    assert "ISVARYAM PRODUCT CATALOG" in cat1


def test_catalog_cache_ttl_and_refresh():
    """Verify cache refreshes when TTL expires."""
    catalog._cached_catalog_text = "ORIGINAL_CACHED_TEXT"
    catalog._last_refresh_time = time.time() - (catalog.CACHE_TTL_SECONDS + 10)

    # Calling get_cached_catalog now must trigger refresh because TTL expired
    refreshed = get_cached_catalog()
    assert refreshed != "ORIGINAL_CACHED_TEXT"
    assert "ISVARYAM PRODUCT CATALOG" in refreshed


def test_catalog_stale_cache_on_db_failure():
    """Verify stale cache is served when DB fails during a refresh."""
    stale_text = "ISVARYAM PRODUCT CATALOG:\n- Stale Cold Pressed Oil: 1L: ₹300"
    catalog._cached_catalog_text = stale_text
    catalog._last_refresh_time = time.time() - (catalog.CACHE_TTL_SECONDS + 100)

    # Simulate DB failure during build_catalog_text
    with patch("catalog.build_catalog_text", side_effect=Exception("Database connection timeout")):
        result = get_cached_catalog()
        # Must return the stale cached version without crashing
        assert result == stale_text


def test_catalog_force_refresh():
    """Verify force=True bypasses the TTL cache check."""
    catalog._cached_catalog_text = "PRE_FORCE_TEXT"
    catalog._last_refresh_time = time.time()  # Brand new timestamp

    # With force=False, returns cached text
    assert get_cached_catalog(force=False) == "PRE_FORCE_TEXT"

    # With force=True, forces rebuild
    forced = get_cached_catalog(force=True)
    assert forced != "PRE_FORCE_TEXT"
    assert "ISVARYAM PRODUCT CATALOG" in forced


def test_system_prompt_structure_and_rules():
    """Verify system prompt contains persona, rules, and filled catalog."""
    assert "{catalog}" in SYSTEM_PROMPT
    prompt = get_system_prompt()
    assert "Isvaryam Assistant" in prompt
    assert "Tanglish" in prompt
    assert "vennai" in prompt
    assert "CATALOG:" in prompt
    assert "Cold-Pressed Groundnut Oil" in prompt
