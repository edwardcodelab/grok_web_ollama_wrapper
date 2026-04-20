# Grok → Ollama Wrapper

**A lightweight bridge that turns Grok (grok.com / x.ai) into a local Ollama-compatible API server.**

Run a FastAPI server on `http://localhost:11434` that fully mimics the Ollama API (`/api/chat`, `/api/generate`, `/api/tags`). A clean userscript handles the actual interaction with the Grok web interface via WebSocket, giving you streaming responses you can use with **Open WebUI**, **LangChain**, **LlamaIndex**, **Ollama clients**, or any tool that expects an Ollama endpoint.

---

## ✨ Features

- ✅ Full streaming support (`/api/chat` with `stream: true`)
- ✅ Drop-in replacement for Ollama (same endpoints and JSON format)
- ✅ Clean response parsing — ignores Grok’s UI buttons/toolbars inside code blocks
- ✅ Simple GUI tester included (`tester.py`)
- ✅ Works with any Grok model (just use model name `"grok"`)
- ✅ Lightweight and easy to run — no heavy dependencies

---

## 📋 Requirements

- Python 3.10+
- Web browser with **Tampermonkey** (or Violentmonkey / Greasemonkey)
- Active Grok account (keep logged in)
- A Grok tab (`https://grok.com` or `https://grok.x.ai`) must stay open while using the bridge

---

## 🚀 Installation & Setup

### 1. Clone or download the repository

### 2. Install dependencies

```bash
# Recommended: use a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install fastapi uvicorn requests pyside6
```

### 3. Install the Userscript

1. Install the **Tampermonkey** extension in your browser
2. Click the Tampermonkey icon → **Create a new script**
3. Delete everything and paste the entire content of **`userscript.txt`**
4. Save the script (it will auto-enable)

### 4. Start the server

```bash
python grok_ollama_wrapper.py
```

You should see:

```
🚀 Starting Grok Ollama Wrapper on http://localhost:11434
   WebSocket bridge on ws://localhost:11434/ws
   Keep grok.com tab open with userscript active!
```

---

## 💡 Usage

### Option A: Quick Test with GUI

```bash
python tester.py
```

A clean chat window opens that streams responses directly from your local bridge.

### Option B: Use with any Ollama-compatible tool

Point your client to:

```
http://localhost:11434
```

**Model name:** `grok`

**Example with `curl` (streaming):**

```bash
curl http://localhost:11434/api/chat -d '{
  "model": "grok",
  "messages": [{"role": "user", "content": "Hello, Grok!"}],
  "stream": true
}'
```

Works perfectly with:
- Open WebUI
- Continue.dev
- LangChain / LlamaIndex
- Anything that supports Ollama’s API

---

## 📁 Project Files

| File                     | Description |
|--------------------------|-------------|
| `grok_ollama_wrapper.py` | Main FastAPI server + WebSocket bridge |
| `userscript.txt`         | Tampermonkey script (V5.5) — optimized for clean markdown extraction |
| `tester.py`              | PySide6 GUI tester with real-time streaming |

---

## 🔧 Technical Approach & Architecture

This project was designed to solve a very specific problem: **xAI does not provide a public API for Grok**, yet many developers and tools expect a local Ollama-style endpoint. Instead of relying on unofficial reverse-engineered APIs (which often break or get blocked), this wrapper uses a **hybrid browser + server architecture** that leverages your existing Grok web session.

### Why This Approach?

- **No official API** → We cannot call Grok directly from Python.
- **Web UI is the only stable interface** → Grok’s chat is fully functional and already handles context, tools, and the latest model updates.
- **Real-time streaming** → Polling would be inefficient; we need true incremental output like native Ollama.
- **Clean output** → Grok’s rendered HTML contains UI noise (copy buttons, toolbars, etc.). We must extract pure markdown.

### High-Level Architecture

```
[Your Tool / Open WebUI / curl]
          ↓ (Ollama API)
    FastAPI Server (port 11434)
          ↓ (WebSocket)
    Tampermonkey Userscript (running on grok.com)
          ↓ (DOM injection)
    Grok Web Chat
          ↓ (MutationObserver)
    Userscript extracts clean markdown
          ↓ (WebSocket chunks)
    FastAPI Server
          ↓ (SSE streaming)
    Back to your tool
```

### Detailed Flow (Step-by-Step)

1. **Request arrives** at `/api/chat` (or `/api/generate`).
2. Server generates a unique `request_id` and stores an `asyncio.Queue` for that request.
3. Server sends a JSON command over the persistent WebSocket (`/ws`) to the connected userscript:
   ```json
   { "type": "send_prompt", "prompt": "...", "request_id": "uuid-here" }
   ```
4. **Userscript** injects the prompt into the Grok chat input field (`ProseMirror` contenteditable) and programmatically clicks Send.
5. A **MutationObserver** (with subtree + characterData watching) is attached to `document.body`.
   - It waits for new `.response-content-markdown` elements (the latest response block).
   - A **debounce timer (150ms)** prevents sending partial/incomplete chunks during rendering.
6. **Custom recursive markdown extractor** (`getMarkdown()`) traverses the DOM:
   - Handles headings, paragraphs, code blocks, tables, etc.
   - **Crucially ignores** UI elements: `.pro-code-toolbar`, buttons, copy icons, etc.
   - Builds clean markdown on the fly (no HTML-to-markdown library needed).
7. New chunks are sent back via WebSocket as:
   ```json
   { "type": "response_chunk", "request_id": "...", "chunk": "new text..." }
   ```
8. When Grok finishes (detected by presence of `.action-buttons.last-response` or copy buttons), the userscript sends a `response_done` signal.
9. Server converts chunks into proper **Server-Sent Events (SSE)** format that Ollama clients expect and closes the stream.

### Key Technical Decisions

- **WebSocket bridge** instead of HTTP polling → true low-latency streaming.
- **MutationObserver + debounce** → catches incremental rendering without busy-waiting.
- **DOM traversal instead of `innerText`** → preserves formatting (code blocks, tables, headings).
- **UUID-based request matching** → supports concurrent requests (future-proof).
- **No external dependencies in userscript** → pure vanilla JS, runs instantly.
- **SSE compatibility layer** in FastAPI → works with every Ollama client out of the box.

### Advantages of This Design

- Uses your **real Grok subscription** (no extra cost or rate-limit tricks).
- Gets the **exact same model** Grok.com uses (always up-to-date).
- Full **streaming** with proper markdown.
- Extremely **lightweight** (no LLM running locally).
- Easy to debug (GUI tester + console logs).

### Limitations & Trade-offs

- Requires a **browser tab with Grok open** (the userscript must stay active).
- Subject to Grok web UI changes (though the V5.5 script is quite resilient).
- Rate limits are whatever Grok.com enforces for your account.
- Slightly higher latency than native Ollama (web round-trip).

This architecture is intentionally simple yet robust — it treats the Grok web UI as a “black-box model server” and focuses all intelligence on clean data extraction and reliable streaming.

---

## ⚠️ Limitations & Notes

- Grok’s web rate limits still apply
- A Grok browser tab must remain open and active
- Responses may be slightly slower than native Ollama (web → local bridge)
- Best used with a dedicated browser profile or pinned tab
- This is an **unofficial** community project — not affiliated with xAI

---

## Contributing

Feel free to open issues or submit pull requests. Improvements to the userscript (better markdown handling, multi-turn support, etc.) are especially welcome!

---

## License

Open source. Use, modify, and share freely.

---

**Enjoy using Grok locally with full Ollama compatibility!** 🚀
```
