# Isvaryam LLM Chatbot 🪔

An intelligent, LLM-powered customer service assistant for **Isvaryam** (Coimbatore, Tamil Nadu), built using Flask, Groq API (`openai/gpt-oss-120b`), and MongoDB.

The chatbot replaces legacy keyword/regex matching with LLM function calling and natural conversation in **English, Tamil script (தமிழ்), and Tanglish** (romanized Tamil, e.g. *"chekku ennai price enna?"*, *"nei"*, *"karupatti"*, *"delivery eppo varum?"*).

---

## 🌟 Key Features

1. **LLM Function Calling via Groq SDK**:
   - `get_product_details(product_name)`: Live price tiers, sizes, descriptions, ingredients, and product images.
   - `get_reviews(product_name, limit=5)`: Verified customer reviews and average star ratings.
   - `get_store_contact()`: Store address, phone, email, and website.
   - `get_delivery_info(city)`: Delivery timelines (Coimbatore: 2 days; other locations: 3–4 days).
   - Maximum 3 tool-calling rounds before forcing a final conversational answer.

2. **Prompt Caching Optimization**:
   - System prompt embeds a compact, alphabetically sorted catalog string at the very beginning to maximize Groq prompt caching efficiency and keep free-tier TPM usage low.
   - Catalog refreshes automatically every 5 minutes with a background in-memory TTL cache.

3. **Multi-Lingual & Tanglish Native**:
   - Accurately interprets colloquial Tamil culinary and oil terms (*chekku ennai*, *kadalai ennai*, *thengai ennai*, *vennai/nei*, *karupatti*, *naatu sakkarai*).
   - Dynamically responds in the exact language and script used by the customer.

4. **Fault-Tolerant Database Layer (`db.py`)**:
   - Lazy connection with `serverSelectionTimeoutMS=3000`.
   - Never crashes on boot if MongoDB is unreachable or if `MONGO_URI` is unconfigured.
   - Built-in static fallback catalog and reviews for seamless continuity.

5. **Reliability & Unmatched Query Logging**:
   - Handles Groq `429` (Rate Limit) and `5xx` (Server Error) with automatic backoff retry.
   - Returns friendly emergency fallback with direct phone/WhatsApp contact if limits are exhausted.
   - Logs unhandled or missing product queries to `logs/unmatched.log` for continuous prompt improvement.

6. **Enterprise Security**:
   - Strict input validation: messages capped at 500 characters; conversation history capped at 8 turns with role validation (`user` / `assistant` only, blocking `system` injection).
   - Per-IP rate limiting with `Flask-Limiter` (10 requests/min, 200 requests/day).
   - Frontend renders user messages strictly via `textContent` (zero DOM XSS), and bot messages through a safe markdown sanitizer.
   - Hardened HTTP security headers (`Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`).

---

## 🏗️ Project Structure

```
├── app.py              # Flask application, route handlers, validation, rate limiting
├── llm.py              # Groq client, tool-calling loop, retry/backoff, fallbacks
├── db.py               # Central MongoDB schema adapters, lazy connection, fallback data
├── catalog.py          # Compact catalog string generator and 5-min TTL cache
├── tools.py            # Tool schemas (Groq function calling) and execution logic
├── prompts.py          # SYSTEM_PROMPT template structured for prompt caching
├── contact.json        # Store contact info (phone, email, website, address)
├── ingredients.json    # Product characteristics, ingredients, and health benefits
├── Procfile            # Gunicorn entrypoint: 'web: gunicorn app:app'
├── requirements.txt    # Python dependencies (removed spacy/nltk; added groq, limiter, etc.)
├── .env.example        # Environment variable template
├── .gitignore          # Git exclusion rules (ignores .env, logs, cache)
├── pytest.ini          # Pytest path configuration
├── static/
│   ├── chat.js         # Frontend client (history management, XSS-safe rendering, chips)
│   └── style.css       # Clean, modern, responsive chat UI styling
├── templates/
│   └── index.html      # Single-page chat interface
├── guardrails/         # Multi-layered Guardrail Harness
│   ├── input_guard.py  # NFKC, zero-width stripping, floods, base64/hex blobs, injection detection
│   ├── history_guard.py# Role enforcement (user/assistant only), length and turn ceilings
│   ├── budget.py       # Daily token budget, session counters, circuit breaker, kill switch
│   ├── tool_guard.py   # Pydantic tool schemas, catalog whitelist, NoSQL sanitization, <tool_data>
│   ├── output_guard.py # Price validation, canary leak detection, medical claim checks, allowlists
│   ├── abuse.py        # Strike counter (3 strikes = 1-hour block per session/IP hash)
│   ├── audit.py        # JSONL audit logger (hashed IPs, truncated queries, no secrets)
│   └── pipeline.py     # Fail-closed guardrail pipeline execution
├── tests/              # Comprehensive test suite (111 unit, integration, and red-team tests)
│   ├── test_app.py
│   ├── test_catalog_and_prompts.py
│   ├── test_db.py
│   ├── test_llm.py
│   ├── test_tools.py
│   ├── test_guardrails_units.py # Independent unit tests for every guardrail module
│   ├── test_red_team.py        # 34 adversarial jailbreaks, NoSQL, coupon manipulation tests
│   ├── test_security_audit.py
│   └── eval_questions.md       # 30 curated English, Tamil, and Tanglish customer test cases
├── scripts/
│   └── run_eval.py     # Evaluation runner sending eval_questions.md to running app
└── logs/
    └── unmatched.log   # Runtime log of fallback/unanswered user queries
```

---

## 🗄️ Database Schema & Assumptions

All schema details are centralized in [db.py](file:///home/onedeck/Documents/isvarayam_chatbot-master/db.py):

- **Database**: `isvaryam`
- **Collection `products`**:
  - `_id`: `ObjectId` (unique identifier)
  - `name`: `str` (e.g., `"Cold-Pressed Groundnut Oil"`)
  - `description`: `str` (detailed description)
  - `quantities`: `List[dict]` with fields `size` (`str`, e.g. `"1L"`) and `price` (`int` / `float`)
  - `images`: `List[str]` (image URLs starting with `https://`)
  - `url`: `str` (optional product page URL)
- **Collection `reviews`**:
  - `_id`: `ObjectId`
  - `productId`: `ObjectId` (references `products._id`)
  - `review`: `str` (customer testimonial text)
  - `rating`: `float` / `int` (star rating from 1 to 5)

*Assumptions*:
- If MongoDB is unconfigured or temporarily down, `db.py` serves a verified static catalog containing Isvaryam's 6 core products with live store links so customer inquiries are never blocked.
- Image URLs returned to the frontend must use the `https://` scheme to satisfy Content Security Policy rules.

---

## ⚙️ Setup & Installation

### 1. Prerequisites
- Python 3.11+ (verified up to Python 3.14)
- A Groq API Key ([https://console.groq.com/keys](https://console.groq.com/keys))
- (Optional) MongoDB Atlas URI

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env`:
```ini
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
PORT=5000
```

### 4. Run Locally
**Using Flask development server:**
```bash
python3 app.py
```
Visit `http://localhost:5000` in your browser.

**Using Gunicorn:**
```bash
gunicorn app:app --bind 0.0.0.0:5000
```

### 5. Run Test Suite
```bash
python3 -m pytest -v
```

---

## 🚀 Deployment

The repository includes a ready-to-deploy [Procfile](file:///home/onedeck/Documents/isvarayam_chatbot-master/Procfile):
```text
web: gunicorn app:app
```

### Deploying on Render / Heroku / Railway
1. Push repository to GitHub or connect directly.
2. Ensure build command installs requirements:
   ```bash
   pip install -r requirements.txt
   ```
3. Set environment variables in the provider's dashboard:
   - `GROQ_API_KEY`: Your Groq API key
   - `GROQ_MODEL`: `openai/gpt-oss-120b` (or swap to any Groq-supported model)
   - `MONGO_URI`: Your MongoDB connection string
4. Health check endpoint: `GET /health`

---

## 📋 File Audit: Changes & Additions

| File | Status | Description |
|---|---|---|
| `app.py` | **Rewritten** | Replaced legacy regex/difflib with Flask-Limiter, strict payload validation, security headers, `/health`, and Groq LLM integration. |
| `llm.py` | **Created** | Groq client, multi-turn tool-calling loop (max 3 rounds), backoff retry for 429/5xx, and unmatched query logging. |
| `db.py` | **Created** | Single source of truth for MongoDB schema adapters, lazy connection, and static product fallback. |
| `catalog.py` | **Created** | Compact, stably sorted catalog builder with a 5-minute memory cache for Groq prompt caching. |
| `tools.py` | **Created** | Groq function calling schemas and execution functions for live prices, reviews, contact, and delivery. |
| `prompts.py` | **Created** | Deterministic system prompt with embedded catalog, Tanglish guidance, guardrails, and tone controls. |
| `contact.json` | **Updated** | Separated `"email"` and `"website"` into distinct keys. |
| `requirements.txt` | **Updated** | Removed unused `spacy` and `nltk`; added `groq`, `flask-limiter`, `python-dotenv`, `pytest`, `gunicorn`. |
| `.env.example` | **Created** | Template for secrets and environment variables. |
| `.gitignore` | **Created** | Prevents committing `.env`, Python bytecode, pytest cache, and log files. |
| `pytest.ini` | **Created** | Pytest path configuration for test execution. |
| `templates/index.html` | **Updated** | Modernized layout with brand header, quick-reply chips, typing indicator, and external script link. |
| `static/style.css` | **Updated** | Enhanced responsive styles for quick chips, message bubbles, image cards, and animated typing bubble. |
| `static/chat.js` | **Created** | Separated client logic: sends last 8 turns of history, renders user input safely with `textContent`, and safe markdown for bot replies. |
| `guardrails/*` | **Created** | Layered guardrail harness: input, history, budget, tool, output, abuse, audit, and pipeline. |
| `tests/test_guardrails_units.py` | **Created** | Unit tests for every guardrail module. |
| `tests/test_red_team.py` | **Created** | 34 adversarial jailbreaks, NoSQL, coupon manipulation, and medical claim tests. |
| `tests/eval_questions.md` | **Created** | 30 curated English, Tamil, and Tanglish customer evaluation test cases. |
| `scripts/run_eval.py` | **Created** | Evaluation runner sending test cases to the running app. |

---

## 🛡️ Guardrails Harness & Security Architecture

The `guardrails/` package implements a **fail-closed, defense-in-depth** harness:

1. **`input_guard.py`**:
   - **Unicode Normalization**: Canonical NFKC expansion, strips zero-width joiners/spaces (`\u200b`, `\u200c`, `\u200d`, `\ufeff`) and control characters.
   - **Length & Flood Limits**: Min 1 character, max 500 characters; detects repeated-character floods ($15+$ identical consecutive characters).
   - **Binary Blobs**: Rejects Base64 chunks ($30+$ chars) and hexadecimal payload streams.
   - **Prompt Injection Defense**: Multi-lingual regex catching English, Tanglish, and Tamil injection phrases (*"ignore previous instructions"*, *"rules-a ignore pannu"*, *"விதிமுறைகளை புறக்கணி"*).

2. **`history_guard.py`**:
   - Enforces valid roles strictly within `{"user", "assistant"}` (blocks `system`, `tool`, or `admin` injection).
   - Sanitizes extra/injected keys, caps history at 8 turns and 1000 characters per turn.

3. **`budget.py`**:
   - **Daily Token Budget**: Configurable via `DAILY_TOKEN_BUDGET` (default: 500,000 tokens/day) with automatic UTC daily rollover.
   - **Session Rate Cap**: Configurable via `SESSION_REQUEST_LIMIT` (default: 50 requests/session).
   - **Circuit Breaker**: Trips to `OPEN` after 5 consecutive Groq failures (60-second cooldown before probe).
   - **Kill Switch**: Setting `LLM_ENABLED=false` immediately bypasses the LLM and serves verified static store assistance.

4. **`tool_guard.py`**:
   - Pydantic validation schemas (`ProductDetailsSchema`, `ReviewsSchema`, `DeliveryInfoSchema`, `StoreContactSchema`).
   - Resolves product queries strictly to a canonical catalog whitelist.
   - Rejects NoSQL injection operators (`$gt`, `$ne`, `$where`, `{`, `}`) before touching the database.
   - Wraps tool outputs in `<tool_data>` delimiters with untrusted-data instructions to prevent indirect prompt injection from review contents.

5. **`output_guard.py`**:
   - **Price Verification**: Extracts all rupee amounts (`₹`, `Rs.`, `INR`) and verifies them against the official catalog. Hallucinated discount prices (e.g. *"Rs. 50"*) are blocked.
   - **Canary Leak Detection**: Cryptographically random runtime canary token placed in the system prompt; trips alarm if exfiltrated.
   - **Medical Claims Check**: Blocks false claims to cure or treat severe diseases (cancer, diabetes, arthritis, hypertension).
   - **Allowlists**: Restricts domains (`isvaryam.com`), phones (`+91 9578822000`), and emails (`support@isvaryam.com`).

6. **`abuse.py`**:
   - In-memory strike tracker per hashed IP / session.
   - 3 strikes for security infractions trigger an automatic **1-hour block**.

7. **`audit.py`**:
   - Records policy violations to `logs/guardrail_audit.jsonl`.
   - Hashes IP addresses with salted SHA-256 and truncates messages to 100 characters (zero PII/secrets logged).

8. **`pipeline.py`**:
   - Wires all guards in series: `edge -> abuse_check -> budget_check -> input_guard -> history_guard -> LLM(tool_guard) -> output_guard`.
   - **Fail-closed**: Any unexpected exception defaults to a safe fallback response without exposing internal errors.

---

## 🧪 Red-Team & Evaluation Suite

- **Unit & Security Tests**: Run all 111 tests:
  ```bash
  python3 -m pytest -v
  ```
- **Red-Team Adversarial Suite**: Run the 34 red-team jailbreak, NoSQL, and coupon manipulation tests:
  ```bash
  python3 -m pytest tests/test_red_team.py -v
  ```
- **Evaluation Runner**: Send 30 realistic customer questions across English, Tamil script, and Tanglish to the running app:
  ```bash
  python3 scripts/run_eval.py
  ```

