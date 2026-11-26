"""Unit tests for llm.py tool loop, fallback handling, retry/backoff, and logging."""

import os
import json
from unittest.mock import MagicMock, patch
from groq import APIStatusError, RateLimitError
import llm


def test_get_model_name():
    """Verify model name fallback and env var override."""
    with patch.dict(os.environ, {"GROQ_MODEL": "llama-3.3-70b-versatile"}):
        assert llm.get_model_name() == "llama-3.3-70b-versatile"


def test_missing_api_key_graceful_fallback():
    """When GROQ_API_KEY is not set, returns friendly fallback without crashing."""
    with patch.dict(os.environ, {"GROQ_API_KEY": ""}, clear=True):
        reply, images = llm.generate_response("Hello")
        assert "maintenance" in reply.lower() or "contact us" in reply.lower()
        assert images == []


def test_rate_limit_backoff_and_fallback():
    """Verify rate limit 429 retries with backoff and then yields busy fallback message."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_client.chat.completions.create.side_effect = RateLimitError(
        message="Rate limit exceeded",
        response=mock_resp,
        body={"error": "Rate limit"}
    )

    with patch("llm.get_groq_client", return_value=mock_client):
        with patch.dict(os.environ, {"GROQ_API_KEY": "dummy_key"}):
            reply, images = llm.generate_response("Check sesame oil price")
            assert "busy" in reply.lower() or "demand" in reply.lower() or "+91 9578822000" in reply
            # Verify retry was attempted (called twice: initial + 1 backoff retry)
            assert mock_client.chat.completions.create.call_count == 2


def test_groq_500_server_error_retry_and_fallback():
    """Verify Groq 500 server error retries once with backoff and returns graceful fallback."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_client.chat.completions.create.side_effect = APIStatusError(
        message="Internal Server Error on Groq",
        response=mock_resp,
        body={"error": "Internal error"}
    )

    with patch("llm.get_groq_client", return_value=mock_client):
        with patch.dict(os.environ, {"GROQ_API_KEY": "dummy_key"}):
            reply, images = llm.generate_response("Groundnut oil price?")
            assert "+91 9578822000" in reply
            assert mock_client.chat.completions.create.call_count == 2


def test_groq_503_service_unavailable_retry_and_fallback():
    """Verify Groq 503 Service Unavailable retries once and falls back."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_client.chat.completions.create.side_effect = APIStatusError(
        message="Service Unavailable",
        response=mock_resp,
        body={"error": "Service unavailable"}
    )

    with patch("llm.get_groq_client", return_value=mock_client):
        with patch.dict(os.environ, {"GROQ_API_KEY": "dummy_key"}):
            reply, images = llm.generate_response("Delivery to Kovai?")
            assert "+91 9578822000" in reply
            assert mock_client.chat.completions.create.call_count == 2


def test_tool_calling_loop_single_round():
    """Verify standard single tool call: tool called, result fed back, final answer returned."""
    mock_client = MagicMock()

    # Round 1 response: Model requests tool call
    tool_call = MagicMock()
    tool_call.id = "call_groundnut_123"
    tool_call.function.name = "get_product_details"
    tool_call.function.arguments = json.dumps({"product_name": "groundnut oil"})

    resp1 = MagicMock()
    resp1.choices = [MagicMock()]
    resp1.choices[0].message.tool_calls = [tool_call]
    resp1.choices[0].message.role = "assistant"
    resp1.choices[0].message.content = None

    # Round 2 response: Model produces final conversational answer
    resp2 = MagicMock()
    resp2.choices = [MagicMock()]
    resp2.choices[0].message.tool_calls = None
    resp2.choices[0].message.role = "assistant"
    resp2.choices[0].message.content = "Cold-Pressed Groundnut Oil is Rs. 310 for 1L and Rs. 160 for 500ml."

    mock_client.chat.completions.create.side_effect = [resp1, resp2]

    with patch("llm.get_groq_client", return_value=mock_client):
        with patch.dict(os.environ, {"GROQ_API_KEY": "dummy_key"}):
            reply, images = llm.generate_response("What is the price of groundnut oil?")

            assert "Groundnut Oil" in reply
            assert "310" in reply
            assert mock_client.chat.completions.create.call_count == 2
            # Verify images extracted from tool call
            assert len(images) > 0
            assert all(img.startswith("https://") for img in images)

            # Verify the second call received the tool execution output
            second_call_messages = mock_client.chat.completions.create.call_args_list[1][1]["messages"]
            tool_msg = next(m for m in second_call_messages if isinstance(m, dict) and m.get("role") == "tool")
            assert tool_msg["tool_call_id"] == "call_groundnut_123"
            assert "Cold-Pressed Groundnut Oil" in tool_msg["content"]


def test_tool_calling_loop_max_3_rounds_enforced():
    """Verify tool-calling loop enforces maximum 3 rounds and forces a final answer."""
    mock_client = MagicMock()

    # Setup tool calls for rounds 1 and 2
    tc1 = MagicMock()
    tc1.id = "tc1"
    tc1.function.name = "get_product_details"
    tc1.function.arguments = json.dumps({"product_name": "sesame oil"})

    resp1 = MagicMock()
    resp1.choices = [MagicMock()]
    resp1.choices[0].message.tool_calls = [tc1]
    resp1.choices[0].message.role = "assistant"
    resp1.choices[0].message.content = None

    tc2 = MagicMock()
    tc2.id = "tc2"
    tc2.function.name = "get_reviews"
    tc2.function.arguments = json.dumps({"product_name": "sesame oil"})

    resp2 = MagicMock()
    resp2.choices = [MagicMock()]
    resp2.choices[0].message.tool_calls = [tc2]
    resp2.choices[0].message.role = "assistant"
    resp2.choices[0].message.content = None

    # Round 3 response: forced text completion (tools=None)
    resp3 = MagicMock()
    resp3.choices = [MagicMock()]
    resp3.choices[0].message.tool_calls = None
    resp3.choices[0].message.role = "assistant"
    resp3.choices[0].message.content = "Sesame oil is Rs. 430/L and has excellent traditional aroma."

    mock_client.chat.completions.create.side_effect = [resp1, resp2, resp3]

    with patch("llm.get_groq_client", return_value=mock_client):
        with patch.dict(os.environ, {"GROQ_API_KEY": "dummy_key"}):
            reply, images = llm.generate_response("Tell me about sesame oil and its reviews")

            assert "Sesame oil" in reply
            # Exactly 3 rounds of calls
            assert mock_client.chat.completions.create.call_count == 3

            # Verify round 3 had tools=None to force final completion
            third_call_kwargs = mock_client.chat.completions.create.call_args_list[2][1]
            assert third_call_kwargs.get("tools") is None


def test_unmatched_query_logging(tmp_path):
    """Test that unanswered or fallback queries are logged to unmatched.log."""
    test_log_file = tmp_path / "unmatched.log"
    with patch("llm.UNMATCHED_LOG_PATH", str(test_log_file)):
        llm.log_unmatched_query("Who won the cricket match?", "OFF_TOPIC", "We specialize in edible oils.")
        assert test_log_file.exists()
        content = test_log_file.read_text()
        assert "Who won the cricket match?" in content
        assert "OFF_TOPIC" in content
