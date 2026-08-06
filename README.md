<div align="center">

<img src="biswalex_logo.svg" width="90" alt="Mastishk logo" />

# Mastishk

**A full-stack AI assistant with multi-provider LLM chat, hybrid RAG document search, and AI-generated presentations.**

[**🚀 Live Demo**](https://frontend-ashen-phi-83.vercel.app/)

</div>

---

## ✨ Features

- 💬 **Multi-model chat** — streamed responses, switch between Groq-hosted models (Llama 3.1/3.3, GPT-OSS 20B/120B) and free OpenRouter models (Nemotron, Gemma) from a dropdown
- 📄 **Document Q&A (RAG)** — upload PDFs, DOCX, PPTX, or images; hybrid **FAISS + BM25** retrieval fused with Reciprocal Rank Fusion, OCR fallback for scanned documents
- 🌐 **Live web search** — automatically triggered for time-sensitive queries (news, scores, "what's happening today")
- 🖼️ **Vision** — upload an image and ask questions about it
- 📊 **AI-generated PowerPoint decks** — describe a topic, get back a real, themed, editable `.pptx`
- 🔐 **Full auth system** — JWT access/refresh tokens, email OTP password reset, email notifications (Resend)
- ☁️ **Cloud-synced chat history** — conversations persist in Postgres and follow you across devices/logins
- 🔗 **Shareable chat links**, 🎨 **9 built-in themes**, 📱 **installable as a PWA**
- 🧩 **Custom plugins** — register your own API endpoint as a callable tool
- 🧠 **Long-term memory** — extracts durable facts from conversations to personalize future chats

---

## 🏗️ Architecture

```
┌─────────────────────┐        Bearer JWT / fetch()        ┌──────────────────────┐
│  Frontend (Vercel)  │ ───────────────────────────────────▶ │   FastAPI backend    │
│  Vanilla JS + CSS    │                                      │   (main.py)          │
└─────────────────────┘                                      └──────────┬───────────┘
                                                                          │
                          ┌───────────────────────────────────────────────┼───────────────────────────┐
                          │                                               │                            │
                 ┌────────▼────────┐                          ┌──────────▼─────────┐        ┌─────────▼─────────┐
                 │  auth.py         │                          │  engine.py           │        │  rag_store.py      │
                 │  JWT / OTP auth  │                          │  LLM orchestration,  │        │  FAISS + BM25       │
                 │                  │                          │  parsing, PPTX gen   │        │  hybrid retrieval   │
                 └────────┬─────────┘                          └──────────┬──────────┘        └─────────┬───────────┘
                          │                                               │                              │
                          ▼                                               ▼                              ▼
                 ┌──────────────────────────────────────────────────────────────────────────────────────────┐
                 │                     PostgreSQL (Supabase) · Groq API · OpenRouter API · Resend            │
                 └──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Vanilla HTML/CSS/JS, [marked.js](https://marked.js.org/) (Markdown), [highlight.js](https://highlightjs.org/) (code), [KaTeX](https://katex.org/) (math), Babel standalone (live React previews) |
| **Backend** | [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) |
| **Database** | PostgreSQL ([Supabase](https://supabase.com/)) via SQLAlchemy ORM |
| **Auth** | PyJWT (access + refresh tokens), PBKDF2-HMAC-SHA256 password hashing |
| **LLM Providers** | [Groq](https://groq.com/) (primary), [OpenRouter](https://openrouter.ai/) (free-tier models) |
| **Embeddings** | [fastembed](https://github.com/qdrant/fastembed) — `BAAI/bge-small-en-v1.5` |
| **Vector search** | [FAISS](https://github.com/facebookresearch/faiss) (cosine similarity) |
| **Keyword search** | [rank_bm25](https://github.com/dorianbrown/rank_bm25) (BM25Okapi) |
| **Document parsing** | pdfplumber, pypdfium2, python-docx, python-pptx, Pillow, pytesseract (OCR) |
| **Presentation generation** | python-pptx |
| **Email** | [Resend](https://resend.com/) API |
| **Containerization** | Docker (`python:3.11-slim`) |
| **Hosting** | Backend on Hugging Face Spaces (Docker SDK) · Frontend on [Vercel](https://frontend-ashen-phi-83.vercel.app/) |

---

## 📂 Project Structure

```
.
├── main.py            # FastAPI app, route definitions
├── chat_routes.py      # Chat session/message CRUD endpoints
├── auth.py              # JWT auth, signup/login, password reset (OTP)
├── db.py                 # SQLAlchemy models + Postgres session management
├── engine.py               # LLM calls, prompt building, doc parsing, PPTX generation
├── rag_store.py              # FAISS + BM25 hybrid document retrieval
├── index.html                  # Frontend (single-file vanilla JS app)
├── manifest.json                # PWA manifest
├── sw.js                          # PWA service worker (pass-through, no caching)
├── Dockerfile                       # Container build
└── requirements.txt                  # Python dependencies
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- A PostgreSQL database (e.g. a free [Supabase](https://supabase.com/) project)
- API keys for [Groq](https://console.groq.com/) and/or [OpenRouter](https://openrouter.ai/)

### 1. Clone & install
```bash
git clone <your-repo-url>
cd mastishk
pip install -r requirements.txt
```

### 2. Configure environment variables
Create a `.env` file in the project root:

```env
# Required
DATABASE_URL=postgresql://user:password@host:5432/dbname
GROQ_API_KEY=your_groq_key

# Optional
OPENROUTER_API_KEY=your_openrouter_key
TAVILY_API_KEY=your_tavily_key
JWT_SECRET=a_long_random_secret
RESEND_API_KEY=your_resend_key
FROM_EMAIL=noreply@yourdomain.com
ADMIN_NOTIFY_EMAIL=you@yourdomain.com
```

> `DATABASE_URL` is required — the app will refuse to start without it (no silent SQLite fallback).

### 3. Run locally
```bash
python main.py
# API available at http://localhost:7860
```

### 4. Run with Docker
```bash
docker build -t mastishk .
docker run -p 7860:7860 --env-file .env mastishk
```

---

## 🔑 API Overview

| Category | Endpoints |
|---|---|
| **Auth** | `POST /auth/signup`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/forgot-password`, `/auth/verify-otp`, `/auth/reset-password`, `GET /auth/me` |
| **Chat** | `POST /chat` (streaming), `POST /quick-task`, `POST /canvas-edit`, `POST /generate-title`, `POST /suggest-followups` |
| **Chat sessions** | `GET/POST /chat-sessions`, `GET/PATCH/DELETE /chat-sessions/{id}`, `GET/POST /chat-sessions/{id}/messages` |
| **Documents** | `POST /upload`, `GET /upload-status/{filename}`, `GET /documents`, `DELETE /documents/{filename}`, `POST /clear` |
| **Generation** | `POST /generate-ppt` (AI-generated PowerPoint) |
| **Utility** | `POST /web-search-quick`, `GET /discover-topics`, `POST /execute-plugin`, `POST /verify-response`, `POST /background-task` |
| **Sharing** | `POST /share`, `GET /share/{share_id}` |

Full request/response schemas are defined via Pydantic models in `main.py`.

---

## 🔒 Security Notes

- All chat data is scoped by `user_id` at the database-query level — one user can never read or write another user's conversations.
- Passwords are hashed with PBKDF2-HMAC-SHA256 (200,000 iterations) + per-user salt.
- Access tokens are short-lived (30 min default); refresh tokens are revocable and stored server-side.
- Login/signup responses never reveal whether an email is already registered.

---

## 📄 License

This project is provided as-is for personal/portfolio use.
