"""Database layer for Isvaryam Chatbot.

Encapsulates all MongoDB connection logic, schema knowledge,
and schema adapters. Ensures lazy, fault-tolerant connections with
short timeouts and fallback defaults so the application never crashes
if MongoDB is unreachable.
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import PyMongoError

logger = logging.getLogger("isvaryam.db")

# Database & Collection Schema Constants
DB_NAME = "isvaryam"
COLLECTION_PRODUCTS = "products"
COLLECTION_REVIEWS = "reviews"

# Schema Field Definitions
FIELD_PRODUCT_ID = "_id"
FIELD_PRODUCT_NAME = "name"
FIELD_PRODUCT_DESC = "description"
FIELD_PRODUCT_QUANTITIES = "quantities"  # List of {"size": str, "price": float|int}
FIELD_PRODUCT_IMAGES = "images"          # List of image URLs

FIELD_REVIEW_ID = "_id"
FIELD_REVIEW_PRODUCT_ID = "productId"
FIELD_REVIEW_TEXT = "review"
FIELD_REVIEW_RATING = "rating"

# Default fallback catalog data when MongoDB is offline or unpopulated
FALLBACK_PRODUCTS: List[Dict[str, Any]] = [
    {
        "_id": "static_groundnut_oil",
        "name": "Cold-Pressed Groundnut Oil",
        "description": "Traditional cold-pressed groundnut oil, naturally rich in Vitamin E, heart-healthy, and ideal for high-heat cooking.",
        "quantities": [
            {"size": "500ml", "price": 160},
            {"size": "1L", "price": 310},
            {"size": "5L", "price": 1500}
        ],
        "images": ["https://isvaryam.com/cdn/shop/files/groundnut_oil.jpg"],
        "url": "https://isvaryam.com/products/cold-pressed-groundnut-oil?sku_id=26795436"
    },
    {
        "_id": "static_coconut_oil",
        "name": "Cold-Pressed Coconut Oil",
        "description": "Pure virgin cold-pressed coconut oil with high lauric acid, excellent for cooking, hair nourishment, and skin care.",
        "quantities": [
            {"size": "500ml", "price": 185},
            {"size": "1L", "price": 360}
        ],
        "images": ["https://isvaryam.com/cdn/shop/files/coconut_oil.jpg"],
        "url": "https://isvaryam.com/products/cold-pressed-coconut-oil?sku_id=24459981"
    },
    {
        "_id": "static_sesame_oil",
        "name": "Wood-Pressed Sesame Oil (Gingelly/Chekku)",
        "description": "Authentic wood-pressed gingelly oil made from premium sesame seeds, rich in antioxidants and calcium, perfect for traditional dishes.",
        "quantities": [
            {"size": "500ml", "price": 220},
            {"size": "1L", "price": 430}
        ],
        "images": ["https://isvaryam.com/cdn/shop/files/sesame_oil.jpg"],
        "url": "https://isvaryam.com/products/cold-pressed-sesame-oil?sku_id=26795647"
    },
    {
        "_id": "static_ghee",
        "name": "Pure Desi Cow Ghee (Bilona Method)",
        "description": "Traditional curd-churned Bilona cow ghee, rich in healthy fats, aromatic, and excellent for digestion and immunity.",
        "quantities": [
            {"size": "250ml", "price": 350},
            {"size": "500ml", "price": 680}
        ],
        "images": ["https://isvaryam.com/cdn/shop/files/desi_cow_ghee.jpg"],
        "url": "https://isvaryam.com"
    },
    {
        "_id": "static_jaggery_powder",
        "name": "Organic Jaggery Powder (Naatu Sakkarai)",
        "description": "Pure unrefined sugarcane jaggery powder, free from chemical clarifying agents and rich in natural iron.",
        "quantities": [
            {"size": "500g", "price": 65},
            {"size": "1kg", "price": 120}
        ],
        "images": ["https://isvaryam.com/cdn/shop/files/jaggery_powder.jpg"],
        "url": "https://isvaryam.com/products/organic-jaggery-powder?sku_id=24463067"
    },
    {
        "_id": "static_super_pack",
        "name": "Super Pack Combo (3x1L Oils)",
        "description": "Value combo pack containing 1 Litre Cold-Pressed Groundnut Oil, 1 Litre Coconut Oil, and 1 Litre Sesame Oil.",
        "quantities": [
            {"size": "3 x 1L Pack", "price": 1050}
        ],
        "images": ["https://isvaryam.com/cdn/shop/files/super_pack_combo.jpg"],
        "url": "https://isvaryam.com/products/super-pack-1-lt-coconut-oil-1-lt-sesame-oil-1-lt-groundnut-oil?sku_id=24633382"
    }
]

# Known product web links
PRODUCT_LINKS = {
    "groundnut oil": "https://isvaryam.com/products/cold-pressed-groundnut-oil?sku_id=26795436",
    "coconut oil": "https://isvaryam.com/products/cold-pressed-coconut-oil?sku_id=24459981",
    "sesame oil": "https://isvaryam.com/products/cold-pressed-sesame-oil?sku_id=26795647",
    "jaggery powder": "https://isvaryam.com/products/organic-jaggery-powder?sku_id=24463067",
    "super pack": "https://isvaryam.com/products/super-pack-1-lt-coconut-oil-1-lt-sesame-oil-1-lt-groundnut-oil?sku_id=24633382",
    "ghee": "https://isvaryam.com"
}

_client: Optional[MongoClient] = None


def get_client() -> Optional[MongoClient]:
    """Lazily initialize and return the MongoClient instance."""
    global _client
    if _client is not None:
        return _client

    mongo_uri = os.environ.get("MONGO_URI")
    if not mongo_uri:
        logger.warning("MONGO_URI environment variable not set. Running in fallback mode.")
        return None

    try:
        # serverSelectionTimeoutMS=3000 ensures quick failure if host is unreachable
        _client = MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=3000,
            connectTimeoutMS=3000,
            socketTimeoutMS=3000,
            connect=False
        )
        return _client
    except Exception as exc:
        logger.error("Failed to initialize MongoClient: %s", exc)
        return None


def get_database():
    """Retrieve the 'isvaryam' database instance safely."""
    client = get_client()
    if client is None:
        return None
    try:
        return client[DB_NAME]
    except Exception as exc:
        logger.error("Could not access database %s: %s", DB_NAME, exc)
        return None


def is_db_connected() -> bool:
    """Check if MongoDB is actively responding."""
    client = get_client()
    if client is None:
        return False
    try:
        client.admin.command("ping")
        return True
    except Exception:
        return False


def normalize_product_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a raw MongoDB product document into a standard dictionary."""
    pid = str(doc.get(FIELD_PRODUCT_ID, ""))
    name = str(doc.get(FIELD_PRODUCT_NAME, "Product"))
    desc = str(doc.get(FIELD_PRODUCT_DESC, ""))
    raw_quantities = doc.get(FIELD_PRODUCT_QUANTITIES, [])
    quantities = []
    if isinstance(raw_quantities, list):
        for q in raw_quantities:
            if isinstance(q, dict):
                quantities.append({
                    "size": str(q.get("size", "")),
                    "price": q.get("price", 0)
                })
    raw_images = doc.get(FIELD_PRODUCT_IMAGES, [])
    images = [img for img in raw_images if isinstance(img, str) and img.startswith("https://")]

    # Match store link
    lower_name = name.lower()
    url = doc.get("url")
    if not url:
        for k, v in PRODUCT_LINKS.items():
            if k in lower_name:
                url = v
                break
    if not url:
        url = "https://isvaryam.com"

    return {
        "id": pid,
        "name": name,
        "description": desc,
        "quantities": quantities,
        "images": images,
        "url": url
    }


def list_all_products() -> List[Dict[str, Any]]:
    """Return all products from MongoDB, falling back to static products if offline."""
    db = get_database()
    if db is not None:
        try:
            cursor = db[COLLECTION_PRODUCTS].find()
            items = [normalize_product_doc(p) for p in cursor]
            if items:
                return items
        except PyMongoError as exc:
            logger.warning("MongoDB error while listing products: %s. Using fallback.", exc)
        except Exception as exc:
            logger.warning("Unexpected error querying products: %s. Using fallback.", exc)

    return [normalize_product_doc(p) for p in FALLBACK_PRODUCTS]


def find_product_by_name(query_name: str) -> Optional[Dict[str, Any]]:
    """Search for a product matching query_name, falling back gracefully."""
    cleaned = query_name.strip().lower()
    if not cleaned:
        return None

    db = get_database()
    if db is not None:
        try:
            # Escape regex characters
            safe_query = re.escape(cleaned)
            doc = db[COLLECTION_PRODUCTS].find_one(
                {FIELD_PRODUCT_NAME: {"$regex": safe_query, "$options": "i"}}
            )
            if doc:
                return normalize_product_doc(doc)
        except PyMongoError as exc:
            logger.warning("MongoDB error while finding product '%s': %s", query_name, exc)
        except Exception as exc:
            logger.warning("Unexpected error finding product: %s", exc)

    # Search in fallback products
    for p in FALLBACK_PRODUCTS:
        p_name = p["name"].lower()
        if cleaned in p_name or p_name in cleaned:
            return normalize_product_doc(p)

    return None


def get_reviews_for_product(product_id_or_name: str, limit: int = 5) -> Dict[str, Any]:
    """Retrieve product reviews and calculate average rating."""
    prod = find_product_by_name(product_id_or_name)
    target_id: Optional[ObjectId] = None
    if prod and prod.get("id"):
        try:
            target_id = ObjectId(prod["id"])
        except Exception:
            target_id = None

    db = get_database()
    reviews_list: List[Dict[str, Any]] = []
    if db is not None and target_id is not None:
        try:
            cursor = db[COLLECTION_REVIEWS].find({FIELD_REVIEW_PRODUCT_ID: target_id}).limit(limit)
            for r in cursor:
                reviews_list.append({
                    "review": str(r.get(FIELD_REVIEW_TEXT, "")),
                    "rating": float(r.get(FIELD_REVIEW_RATING, 5.0))
                })
        except Exception as exc:
            logger.warning("Could not fetch reviews for product %s: %s", product_id_or_name, exc)

    if reviews_list:
        avg_rating = round(sum(r["rating"] for r in reviews_list) / len(reviews_list), 1)
        return {
            "product_name": prod["name"] if prod else product_id_or_name,
            "average_rating": avg_rating,
            "total_reviews": len(reviews_list),
            "reviews": reviews_list
        }

    return {
        "product_name": prod["name"] if prod else product_id_or_name,
        "average_rating": None,
        "total_reviews": 0,
        "reviews": []
    }

