# BiswaLex AI

BiswaLex is a full-stack, ChatGPT-style AI assistant with document-aware RAG (Retrieval-Augmented Generation), live web search, OCR-based file ingestion, and a fast, installable Progressive Web App (PWA) frontend.

It pairs a **FastAPI backend** (Groq-hosted LLMs + a lightweight in-memory vector index) with a **single-file HTML/CSS/JS frontend** that works great on desktop and mobile, and can be installed like a native app.

Live Demo
App: https://frontend-five-ruby-23.vercel.app/

<img width="512" height="512" alt="WhatsApp Image 2026-07-05 at 2 48 47 PM" src="https://github.com/user-attachments/assets/fac54543-fd37-4928-804a-c003818fc30d" />

## ✨ Features

- **Multi-model chat** — switch between several free-tier Groq models (Llama 3.3 70B, Llama 3.1 8B Instant, Llama 4 Scout, Qwen3 32B, Gemma2 9B, DeepSeek R1 Distill 70B) right from the UI.
- **Streaming responses** via Server-Sent Events (SSE) for a real-time, token-by-token chat feel.
- **Document-aware RAG**
  - Drop files into a `documents/` folder to build a persistent base knowledge index.
  - Upload PDFs, DOCX, TXT/MD, or images directly in the chat — they're chunked, embedded, and indexed on the fly.
  - Multi-document support: ask about a specific file by name, or use natural phrases like *"this pdf"* / *"the attached document"*, which resolve to the most recently uploaded file (like ChatGPT/Claude/Gemini).
  - Comparative queries ("compare both files", "across all documents") automatically pull from every uploaded document.
  - Summary-style requests ("summarize", "key points", "tl;dr") use the full document text instead of similarity-matched chunks.
- **OCR fallback** — scanned/image-based PDFs and photos are automatically run through Tesseract OCR when normal text extraction comes up empty.
- **Live web search** (via Tavily) for time-sensitive queries — news, prices, live scores, current events — with strict guardrails so the model never guesses a "final" sports result from in-progress/live data.
- **Installable PWA** — manifest + service worker provide an app shell cache, offline-friendly loading, and "Add to Home Screen" support on mobile.
- **Conversation management** — multiple chats, rename/search history, export chat as Markdown, and shareable read-only chat links.
- **Light/Dark theme** toggle.

---

## 🏗️ Architecture

```
┌─────────────────────────┐        HTTPS/SSE        ┌───────────────────────────┐
│  Frontend (index.html)  │ <----------------------> │  Backend (FastAPI)        │
│  - Vanilla JS + Marked  │                          │  - main.py (routes)       │
│  - highlight.js, KaTeX  │                          │  - engine.py (RAG + LLM)  │
│  - PWA (manifest, sw.js)│                          │                           │
└─────────────────────────┘                          └───────────┬───────────────┘
                                                                   │
                                                    ┌──────────────┼──────────────┐
                                                    │              │              │
                                              ┌─────▼────┐   ┌─────▼─────┐  ┌─────▼─────┐
                                              │  Groq    │   │  Tavily   │  │ fastembed │
                                              │  (LLMs)  │   │ (web srch)│  │ (embeddings)│
                                              └──────────┘   └───────────┘  └───────────┘
```

- **`main.py`** — FastAPI app exposing chat, upload, document management, and health endpoints.
- **`engine.py`** — core logic: file parsing/OCR, chunking, embedding, cosine-similarity retrieval, web search, and the Groq chat/streaming pipeline.
- **`index.html`** — the entire frontend (UI, styling, and client logic) in one file.
- **`manifest.json` / `sw.js`** — PWA install metadata and offline app-shell caching.

---

## 📂 Project Structure

```
.
├── main.py            # FastAPI app & API routes
├── engine.py           # RAG pipeline, file parsing/OCR, LLM + web search logic
├── index.html          # Frontend chat UI (PWA)
├── manifest.json        # PWA manifest
├── sw.js                # Service worker (app-shell caching)
├── icon-192.png         # App icon (192x192)
├── icon-512.png         # App icon (512x512)
├── documents/            # (optional) drop files here for a persistent base RAG index
└── .env                  # API keys (not committed)
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- A free [Groq API key](https://console.groq.com/)
- (Optional, for live web search) A [Tavily API key](https://tavily.com/)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed and on your `PATH` (needed for scanned PDFs/images)

### 1. Clone the repo

```bash
git clone (https://github.com/ABiswajitMohapatra/Large-Language-Model/tree/main)
cd biswalex-ai
```

### 2. Install backend dependencies

```bash
pip install fastapi uvicorn python-multipart groq fastembed pdfplumber pypdfium2 pillow pytesseract python-docx python-dotenv requests numpy
```

> 💡 Consider generating a `requirements.txt` with `pip freeze > requirements.txt` once your environment is set up.

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here   # optional, enables live web search
PORT=7860                                  # optional, defaults to 7860
```

### 4. (Optional) Seed the base knowledge index

Place any PDFs, DOCX, TXT, or MD files into a `documents/` folder next to `engine.py`. They'll be indexed automatically on first request.

### 5. Run the backend

```bash
python main.py
```

The API will be available at `http://localhost:7860`. Check `http://localhost:7860/` for a health check and `http://localhost:7860/rag-status` to confirm your `documents/` folder is being indexed correctly.

### 6. Run the frontend

`index.html` is a static file — open it directly in a browser, or serve it with any static file server:

```bash
python -m http.server 8080
```

> ⚠️ Before deploying, update the `API_URL` constant near the top of the `<script>` section in `index.html` to point at your backend's URL.

---

## 🔌 API Reference

| Method   | Endpoint                | Description                                             |
|----------|--------------------------|----------------------------------------------------------|
| `GET`    | `/`                      | Health check; returns backend status and default model  |
| `GET`    | `/models`                | List available LLM models                                |
| `GET`    | `/rag-status`            | Debug view into the folder-based RAG index                |
| `POST`   | `/chat`                  | Send a message; returns a streaming SSE response          |
| `POST`   | `/upload`                | Upload a document (PDF/DOCX/TXT/MD/image) for RAG          |
| `GET`    | `/documents`             | List currently uploaded documents                          |
| `DELETE` | `/documents/{filename}`  | Remove a specific uploaded document                        |
| `POST`   | `/clear`                 | Clear all uploaded documents                                |

### Example: chat request

```bash
curl -X POST http://localhost:7860/chat \
  -H "Content-Type: application/json" \
  -d '{
        "query": "What is retrieval-augmented generation?",
        "history": [],
        "model": "llama-3.3-70b-versatile"
      }'
```

---

## 📱 PWA / Installability

BiswaLex ships with a `manifest.json` and `sw.js` service worker, so it can be installed as a standalone app on desktop and mobile (Add to Home Screen). The service worker caches the app shell (`index.html`, manifest, icons) for fast, offline-tolerant loading, while API calls always go straight to the network.

---

## 🛠️ Tech Stack

- **Backend:** FastAPI, Groq SDK, fastembed, pdfplumber, pypdfium2, pytesseract, python-docx
- **Frontend:** Vanilla JS/HTML/CSS, marked.js (Markdown rendering), highlight.js (syntax highlighting), KaTeX (math rendering)
- **Search:** Tavily Search API
- **PWA:** Web App Manifest + Service Worker

---

## 🗺️ Roadmap Ideas

- [ ] Persistent (disk/db-backed) document storage instead of in-memory
- [ ] User authentication and per-user document spaces
- [ ] `requirements.txt` / Dockerfile for one-command deploys
- [ ] Configurable embedding/chunking parameters via the UI

---

## 📄 License

Add a license of your choice (e.g. MIT) — see [choosealicense.com](https://choosealicense.com/) for help picking one.

---

## 🙏 Acknowledgements

- [Groq](https://groq.com/) for blazing-fast LLM inference
- [Tavily](https://tavily.com/) for the web search API
- [fastembed](https://github.com/qdrant/fastembed) for lightweight local embeddings
