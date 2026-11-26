"""Tool definitions and implementations for Groq function calling.

Ensures the LLM accesses ground-truth product prices, customer reviews,
contact details, and delivery timelines rather than hallucinating live data.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional
import db

logger = logging.getLogger("isvaryam.tools")

CONTACT_FILE = os.path.join(os.path.dirname(__file__), "contact.json")
INGREDIENTS_FILE = os.path.join(os.path.dirname(__file__), "ingredients.json")


def load_contact_data() -> Dict[str, str]:
    """Load store contact details from contact.json."""
    try:
        if os.path.exists(CONTACT_FILE):
            with open(CONTACT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as exc:
        logger.error("Failed to load contact.json: %s", exc)
    return {
        "phone": "+91 9578822000",
        "email": "support@isvaryam.com",
        "website": "https://isvaryam.com/",
        "address": "isvaryam, 10 e, Ondipudur-Irugur Rd, Coimbatore, Irugur, Tamil Nadu 641103"
    }


def load_ingredients_data() -> Dict[str, List[str]]:
    """Load product ingredients mapping from ingredients.json."""
    try:
        if os.path.exists(INGREDIENTS_FILE):
            with open(INGREDIENTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as exc:
        logger.error("Failed to load ingredients.json: %s", exc)
    return {}


# Tool implementations

def get_product_details(product_name: str = "") -> Dict[str, Any]:
    """Retrieve verified price tiers, sizes, description, image, and ingredients."""
    if not isinstance(product_name, str):
        product_name = str(product_name or "")

    prod = db.find_product_by_name(product_name)
    if not prod:
        return {
            "found": False,
            "message": f"Product '{product_name}' was not found in the Isvaryam catalog.",
            "available_products": [
                "Cold-Pressed Groundnut Oil",
                "Cold-Pressed Coconut Oil",
                "Wood-Pressed Sesame Oil (Gingelly/Chekku)",
                "Pure Desi Cow Ghee (Bilona)",
                "Organic Jaggery Powder (Naatu Sakkarai)",
                "Super Pack Combo (3x1L Oils)"
            ]
        }

    ingredients_map = load_ingredients_data()
    ingredients: List[str] = []
    prod_name_lower = prod["name"].lower()
    for key, ing_list in ingredients_map.items():
        if key in prod_name_lower:
            ingredients = ing_list
            break

    # Validate image URL starts with https
    valid_images = [img for img in prod.get("images", []) if isinstance(img, str) and img.startswith("https://")]

    return {
        "found": True,
        "name": prod["name"],
        "description": prod.get("description", ""),
        "quantities": prod.get("quantities", []),
        "images": valid_images,
        "ingredients": ingredients,
        "product_url": prod.get("url", "https://isvaryam.com")
    }


def get_reviews(product_name: str = "", limit: int = 5) -> Dict[str, Any]:
    """Retrieve average customer rating and recent reviews for a product."""
    if not isinstance(product_name, str):
        product_name = str(product_name or "")
    try:
        limit_val = int(limit)
    except (ValueError, TypeError):
        limit_val = 5
    limit = min(max(limit_val, 1), 10)
    review_data = db.get_reviews_for_product(product_name, limit=limit)
    if review_data.get("total_reviews", 0) == 0:
        return {
            "product_name": review_data.get("product_name", product_name),
            "total_reviews": 0,
            "average_rating": None,
            "message": f"No reviews have been recorded yet for {product_name}."
        }
    return review_data


def get_store_contact() -> Dict[str, str]:
    """Get verified contact details, physical address, and official website."""
    return load_contact_data()


def get_delivery_info(city: Optional[str] = None) -> Dict[str, Any]:
    """Provide verified shipping and delivery timelines based on customer location."""
    if city is not None and not isinstance(city, str):
        city = str(city)
    city_str = (city or "").strip().lower()
    if "coimbatore" in city_str or "kovai" in city_str:
        return {
            "location": "Coimbatore (Local Delivery)",
            "estimated_days": "2 business days",
            "notes": "Fast local dispatch within Coimbatore."
        }
    elif city_str:
        return {
            "location": city.strip().title(),
            "estimated_days": "3 to 4 business days",
            "notes": "Safe, leak-proof courier packaging delivered across Tamil Nadu and all other states in India."
        }
    else:
        return {
            "location": "All Locations",
            "estimated_days": "2 days for Coimbatore; 3 to 4 days for other cities across India.",
            "notes": "Dispatched promptly via reliable courier partners with protective packaging."
        }


# Tool Dispatch Table
TOOL_FUNCTIONS = {
    "get_product_details": get_product_details,
    "get_reviews": get_reviews,
    "get_store_contact": get_store_contact,
    "get_delivery_info": get_delivery_info,
}


def execute_tool(tool_name: str, arguments: Any) -> str:
    """Execute a tool by name with arguments and return JSON string result."""
    func = TOOL_FUNCTIONS.get(tool_name)
    if not func:
        return json.dumps({"error": f"Tool '{tool_name}' not implemented"})
    if not isinstance(arguments, dict):
        arguments = {}
    try:
        result = func(**arguments)
        return json.dumps(result, ensure_ascii=False)
    except TypeError as te:
        logger.error("Argument error executing %s: %s", tool_name, te)
        return json.dumps({"error": f"Invalid arguments for {tool_name}: {str(te)}"})
    except Exception as exc:
        logger.error("Error executing %s: %s", tool_name, exc)
        return json.dumps({"error": f"Failed to execute {tool_name}: {str(exc)}"})


# Groq Function Calling Schema Definitions
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_product_details",
            "description": "Fetch live pricing tiers, available sizes, description, image, and ingredients for an Isvaryam product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "Name or synonym of the product (e.g. 'groundnut oil', 'sesame oil', 'coconut oil', 'ghee', 'jaggery powder', 'super pack')"
                    }
                },
                "required": ["product_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_reviews",
            "description": "Fetch customer reviews and average rating for an Isvaryam product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "Name of the product to fetch reviews for"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of reviews to retrieve (1-10, default 5)"
                    }
                },
                "required": ["product_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_store_contact",
            "description": "Retrieve verified store contact information: phone number, email, website URL, and store address in Coimbatore.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_delivery_info",
            "description": "Get estimated delivery timeline and shipping info based on the customer's city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The destination city or location (e.g. 'Coimbatore', 'Chennai', 'Bangalore')"
                    }
                }
            }
        }
    }
]

