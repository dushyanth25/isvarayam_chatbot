# Isvaryam Chatbot (Flask + TinyLlama, CPU‑only)

Lightweight customer‑assistant chatbot that runs entirely on CPU and fits the **Render Free Tier**.

## ✨ Features
* Rule‑based quick answers (prices, greetings …).
* TinyLlama‑1.1B‑Chat (Q4 GGUF) fallback for everything else.
* MongoDB Atlas for products & reviews.
* No GPU, ≤ 1.6 GB RAM at runtime.

## 🔧 Local run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
mkdir -p models
wget -O models/tinyllama.gguf \
  https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-GGUF/resolve/main/tinyllama-1.1b-chat.Q4_K_M.gguf

export MONGO_URI="mongodb+srv://<user>:<pass>@cluster.mongodb.net/isvaryam"
flask --app app run
