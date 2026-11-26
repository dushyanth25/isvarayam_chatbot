"""Unit tests for db.py schema adapters and fallback resilience."""

import db


def test_db_fallback_when_offline():
    """Verify that database calls return clean fallback data without crashing."""
    products = db.list_all_products()
    assert isinstance(products, list)
    assert len(products) >= 6

    # Verify standard products are present
    product_names = [p["name"].lower() for p in products]
    assert any("groundnut" in name for name in product_names)
    assert any("coconut" in name for name in product_names)
    assert any("sesame" in name for name in product_names)
    assert any("ghee" in name for name in product_names)
    assert any("jaggery" in name for name in product_names)


def test_find_product_by_name():
    """Verify product lookups with various name variations."""
    prod = db.find_product_by_name("groundnut oil")
    assert prod is not None
    assert "Groundnut" in prod["name"]
    assert len(prod["quantities"]) > 0

    # Test non-existent product
    missing = db.find_product_by_name("non_existent_item_xyz")
    assert missing is None


def test_get_reviews_fallback():
    """Verify reviews adapter handles missing reviews gracefully."""
    reviews_info = db.get_reviews_for_product("groundnut oil", limit=5)
    assert isinstance(reviews_info, dict)
    assert "average_rating" in reviews_info
    assert "reviews" in reviews_info


def test_normalize_product_doc():
    """Verify schema normalization handles varied types safely."""
    raw_doc = {
        "_id": "custom_123",
        "name": "Pure Sesame Oil",
        "description": "Wood pressed",
        "quantities": [{"size": "1L", "price": 400}],
        "images": ["https://isvaryam.com/sesame.jpg", "http://insecure.com/bad.jpg", 123]
    }
    normalized = db.normalize_product_doc(raw_doc)
    assert normalized["id"] == "custom_123"
    assert normalized["name"] == "Pure Sesame Oil"
    assert len(normalized["quantities"]) == 1
    # Only https images must be kept
    assert normalized["images"] == ["https://isvaryam.com/sesame.jpg"]

