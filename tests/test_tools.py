"""Unit tests for tool definitions and executions."""

import json
import tools


def test_get_product_details_found():
    """Test get_product_details returns pricing and ingredients."""
    result = tools.get_product_details("coconut oil")
    assert result["found"] is True
    assert "Coconut" in result["name"]
    assert len(result["quantities"]) > 0
    assert isinstance(result["ingredients"], list)


def test_get_product_details_not_found():
    """Test get_product_details returns clear not found message."""
    result = tools.get_product_details("unknown_engine_oil")
    assert result["found"] is False
    assert "available_products" in result


def test_get_store_contact():
    """Test store contact returns split email and website keys."""
    contact = tools.get_store_contact()
    assert "+91" in contact["phone"]
    assert "@" in contact["email"]
    assert "http" in contact["website"]
    assert "Coimbatore" in contact["address"]


def test_get_delivery_info():
    """Test delivery timeline distinction between Coimbatore and other cities."""
    cbe_info = tools.get_delivery_info("Coimbatore")
    assert "2 business days" in cbe_info["estimated_days"]

    kovai_info = tools.get_delivery_info("Kovai")
    assert "2 business days" in kovai_info["estimated_days"]

    chennai_info = tools.get_delivery_info("Chennai")
    assert "3 to 4 business days" in chennai_info["estimated_days"]

    general_info = tools.get_delivery_info("")
    assert "2 days for Coimbatore" in general_info["estimated_days"]


def test_execute_tool_dispatch():
    """Test tool execution wrapper with json output."""
    raw_res = tools.execute_tool("get_delivery_info", {"city": "Madurai"})
    parsed = json.loads(raw_res)
    assert "3 to 4 business days" in parsed["estimated_days"]

    unknown_res = tools.execute_tool("invalid_tool", {})
    assert "not implemented" in unknown_res

