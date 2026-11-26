#!/usr/bin/env python3
"""Evaluation runner for Isvaryam Chatbot.

Sends the 30 curated evaluation questions from tests/eval_questions.md to the
running Flask application and prints each response for manual inspection.
"""

import argparse
import os
import sys
import time
from typing import Dict, List, Optional
import requests

EVAL_FILE = os.path.join(os.path.dirname(__file__), "..", "tests", "eval_questions.md")
DEFAULT_URL = os.environ.get("CHATBOT_URL", "http://127.0.0.1:5000/chatbot")


def parse_eval_questions(filepath: str) -> List[Dict[str, str]]:
    """Parse the markdown table from tests/eval_questions.md into test items."""
    questions: List[Dict[str, str]] = []
    if not os.path.exists(filepath):
        print(f"Error: Evaluation file not found at {filepath}", file=sys.stderr)
        return questions

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Match table row format: | # | Category | Language | Question | Expected |
            if line.startswith("|") and not line.startswith("| #") and not line.startswith("|---"):
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 5:
                    q_num = parts[0]
                    category = parts[1].replace("*", "")
                    lang = parts[2]
                    query = parts[3]
                    expected = parts[4]
                    questions.append({
                        "id": q_num,
                        "category": category,
                        "language": lang,
                        "query": query,
                        "expected": expected
                    })
    return questions


def run_evaluation(
    url: str,
    delay: float = 0.5,
    category_filter: Optional[str] = None
) -> None:
    """Send evaluation questions to the chatbot endpoint and print results."""
    questions = parse_eval_questions(EVAL_FILE)
    if not questions:
        print("No evaluation questions found to execute.", file=sys.stderr)
        return

    if category_filter:
        questions = [q for q in questions if category_filter.lower() in q["category"].lower()]
        print(f"Filtering evaluation questions by category: {category_filter}")

    print("=" * 80)
    print(f"ISVARYAM CHATBOT EVALUATION RUNNER")
    print(f"Target Endpoint: {url}")
    print(f"Total Test Cases: {len(questions)}")
    print(f"Inter-query Delay: {delay}s")
    print("=" * 80)

    # Check endpoint reachability first
    health_url = url.replace("/chatbot", "/health")
    try:
        health_resp = requests.get(health_url, timeout=3.0)
        print(f"Server Health Check: HTTP {health_resp.status_code} ({health_resp.json().get('status', 'unknown')})")
    except Exception as exc:
        print(f"⚠️ Warning: Could not reach health endpoint at {health_url}: {exc}")
        print("Please ensure the Flask app is running (e.g. `python3 app.py`).\n")

    passed_count = 0
    failed_count = 0
    latencies: List[float] = []

    for idx, item in enumerate(questions, 1):
        print(f"\n[{item['id']}/30] [{item['category']}] ({item['language']})")
        print(f"Q: \"{item['query']}\"")
        print(f"Expected: {item['expected']}")

        start_time = time.time()
        try:
            resp = requests.post(
                url,
                json={"message": item["query"]},
                headers={"Content-Type": "application/json"},
                timeout=20.0
            )
            elapsed_ms = round((time.time() - start_time) * 1000, 1)
            latencies.append(elapsed_ms)

            if resp.status_code == 200:
                data = resp.json()
                reply = data.get("response", "").strip()
                images = data.get("images", [])

                print(f"Status: HTTP {resp.status_code} ({elapsed_ms} ms)")
                print(f"Reply:\n{reply}")
                if images:
                    print(f"Images: {images}")
                passed_count += 1
            else:
                print(f"⚠️ Status: HTTP {resp.status_code} ({elapsed_ms} ms)")
                print(f"Response: {resp.text}")
                failed_count += 1

        except requests.exceptions.ConnectionError:
            print(f"❌ Connection Error: Unable to reach {url}. Is the server running?")
            failed_count += 1
            break
        except requests.exceptions.Timeout:
            print(f"❌ Request Timed Out (> 20s)")
            failed_count += 1
        except Exception as exc:
            print(f"❌ Error during request: {exc}")
            failed_count += 1

        print("-" * 80)
        if idx < len(questions) and delay > 0:
            time.sleep(delay)

    # Summary
    print("\n" + "=" * 80)
    print("EVALUATION SUMMARY")
    print(f"Completed Queries: {passed_count + failed_count}/{len(questions)}")
    print(f"Success (200 OK):  {passed_count}")
    print(f"Failures:          {failed_count}")
    if latencies:
        avg_latency = round(sum(latencies) / len(latencies), 1)
        print(f"Average Latency:   {avg_latency} ms")
    print("=" * 80)
    print("Please review the printed responses above against the 'Expected' criteria.")


def main():
    parser = argparse.ArgumentParser(description="Run Isvaryam Chatbot evaluation suite.")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Chatbot endpoint URL (default: {DEFAULT_URL})")
    parser.add_argument("--delay", type=float, default=6.5, help="Delay in seconds between requests to respect rate limits (default: 6.5s)")
    parser.add_argument("--category", default=None, help="Optional filter by category (e.g. Pricing, Delivery, Vennai)")
    args = parser.parse_args()

    run_evaluation(
        url=args.url,
        delay=args.delay,
        category_filter=args.category
    )


if __name__ == "__main__":
    main()

