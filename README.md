# Isvaryam AI Chatbot

Customer support assistant for **Isvaryam** (Coimbatore, Tamil Nadu), built with **Flask**, **Groq API**, and **MongoDB**. Supports natural conversations in **English, Tamil (தமிழ்), and Tanglish** for cold-pressed oils, pure cow ghee, and organic jaggery.

---

## Core Features

- **Groq Function Calling (`llm.py`, `tools.py`)**: Live lookups for product prices/sizes (`get_product_details`), customer ratings (`get_reviews`), store contact (`get_store_contact`), and delivery timelines (`get_delivery_info`).
- **Prompt Caching (`catalog.py`, `prompts.py`)**: Deterministic, 5-minute TTL-cached catalog embedded in the system prompt.
- **Fault-Tolerant Database (`db.py`)**: Lazy MongoDB connection (`serverSelectionTimeoutMS=3000`) with automatic static catalog fallback if MongoDB is unavailable.
- **Guardrails Harness (`guardrails/`)**: Fail-closed pipeline with input normalization/injection filtering, history role enforcement, daily token budget & circuit breaker, Pydantic/NoSQL tool validation, output price/canary/medical-claim checks, rate limiting, and JSONL audit logging.

---

## Project Structure

```text
├── app.py              # Flask entrypoint, security headers, rate limiting, /health, /chatbot
├── llm.py              # Groq client, tool-calling loop (max 3 rounds), retry/fallback
├── db.py               # MongoDB connection, schema adapters, static fallback data
├── catalog.py          # 5-minute TTL-cached compact catalog builder
├── tools.py            # Groq tool definitions and implementations
├── prompts.py          # System prompt template
├── guardrails/         # Input, history, budget, tool, output, abuse, audit, pipeline
├── static/             # chat.js, style.css
├── templates/          # index.html
├── tests/              # Unit, integration, security, and red-team test suite
├── scripts/run_eval.py # Evaluation runner using tests/eval_questions.md
├── contact.json        # Store contact details
├── ingredients.json    # Product ingredients & highlights
├── Procfile            # Gunicorn entrypoint
└── requirements.txt    # Python dependencies
```

---

## Setup & Run Locally

**Prerequisites:** Python 3.11+ and a [Groq API key](https://console.groq.com/keys).

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create `.env`:**
   ```ini
   GROQ_API_KEY=gsk_your_groq_api_key
   GROQ_MODEL=openai/gpt-oss-120b
   MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority
   PORT=5000
   ```

3. **Run the app:**
   ```bash
   python3 app.py
   ```
   Open `http://localhost:5000`.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | Yes | — | Groq API key |
| `GROQ_MODEL` | No | `openai/gpt-oss-120b` | Groq model identifier |
| `MONGO_URI` | No | — | MongoDB connection string (falls back to static catalog if omitted) |
| `LLM_ENABLED` | No | `true` | Kill switch (`false` returns static fallback replies) |
| `DAILY_TOKEN_BUDGET` | No | `500000` | Daily token cap |
| `SESSION_REQUEST_LIMIT` | No | `50` | Max requests per session |
| `GUARDRAIL_SALT` | No | `isvaryam_salt_cbe_2026` | Salt for hashing IPs/session IDs in audit logs |
| `PORT` | No | `5000` | Server port |

---

## Deployment (Render)

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn app:app --workers 1 --threads 4 --bind 0.0.0.0:$PORT --timeout 60`
- **Health Check Path:** `/health`

---

## Testing

```bash
# Run full test suite (unit, integration, security, red-team)
python3 -m pytest -v

# Run evaluation questions against a running server
python3 scripts/run_eval.py
```
