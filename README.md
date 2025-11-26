# Mingjing AI — Backend (FastAPI + MongoDB)

**A production-hardened API gateway for AI-guided personal growth and consciousness awakening.**

This FastAPI service powers the Mingjing platform with resilient LLM integration, intelligent context management, session persistence, and media processing. Designed for stability under real-world network conditions with comprehensive rate limiting and error handling.

---

## 🎯 Overview

This backend provides:

- **AI chat gateway** with streaming/non-streaming modes
- **Session management** with auto-titling and history persistence
- **Document processing** (DOCX text extraction)
- **Voice transcription** (Whisper STT proxy with optional audio enhancement)
- **Context orchestration** with intelligent prompt injection and memory management
- **Rate limiting** and security safeguards for production deployment

---

## ✨ Key Features

### 🧠 AI Chat Gateway

- **Multi-provider support**: OpenAI API with custom base URL override
- **Context management**: Intelligent history composition per session
- **Prompt injection**: Auto-switching between conversation and document-analysis modes
- **Memory summarization**: Optional background task for long conversations
- **Streaming & non-streaming**: SSE streaming with graceful fallback
- **Error resilience**: Friendly Chinese error messages with retry guidance

### 📂 Session Management

- **CRUD operations**: Create, list, rename, delete sessions
- **Auto-titling**: First user message generates session title via LLM
- **Message persistence**: MongoDB storage with user/session scoping
- **Preview generation**: Session list includes last message preview and count
- **Timestamp tracking**: `created_at`, `updated_at` for sorting and display

### 📄 File Processing

- **DOCX extraction**: `python-docx` parsing with 1MB size limit
- **Text normalization**: Clean extraction of paragraphs and formatting
- **Fast response**: Lightweight endpoint optimized for demo use
- **Security**: File type validation and payload size enforcement

### 🎤 Voice Transcription

- **Whisper proxy**: OpenAI Whisper API integration
- **Audio enhancement** (optional): ffmpeg preprocessing with VAD (voice activity detection)
- **Format support**: Handles common audio formats (webm, mp3, wav, m4a)
- **Rate limiting**: 10 requests/minute to prevent abuse

### 🔒 Security & Resilience

- **Rate limiting**: Per-endpoint throttling via `slowapi`
  - Chat: 30 requests/minute
  - DOCX: 20 requests/minute
  - STT: 10 requests/minute
- **CORS configuration**: Wildcard for development, customizable for production
- **JWT authentication**: Token-based user identification
- **Input validation**: Pydantic models with strict type checking
- **HTTP hardening**: HTTP/2 disabled, keep-alive off, retry with exponential backoff

### 🧩 Context Management

- **History composition**: Fetch last N messages from session
- **Document mode detection**: Auto-detect document markers in user message
- **System prompt switching**: Different prompts for conversation vs. document analysis
- **Memory integration**: Optional summarization for long-running sessions
- **Token optimization**: History trimming to stay within model limits

---

## 🛠 Technology Stack

### Core Framework

- **FastAPI** 0.x — Async Python web framework with auto-docs
- **Starlette** — ASGI toolkit (underlying FastAPI)
- **Uvicorn** — Lightning-fast ASGI server
- **Pydantic** — Data validation and settings management

### Database & Persistence

- **MongoDB** — NoSQL database for sessions and messages
- **motor** — Async MongoDB driver for Python
- **pymongo** — Synchronous MongoDB operations (fallback)

### HTTP & Network

- **httpx** — Modern async HTTP client with retry logic
- **requests** — Synchronous fallback for network resilience
- **python-multipart** — Multipart form data parsing (file uploads)

### AI & Media Processing

- **OpenAI API** — LLM chat completions and Whisper STT
- **python-docx** — DOCX text extraction
- **ffmpeg** (optional) — Audio preprocessing for transcription

### Security & Utilities

- **slowapi** — In-memory rate limiting
- **python-jose** — JWT token handling
- **passlib** — Password hashing (bcrypt)
- **python-dotenv** — Environment variable management
- **dnspython** — DNS lookups for MongoDB connection strings

### Network Resilience Strategy

- **HTTP/2 disabled** — Avoids protocol-level issues in unstable networks
- **Keep-alive disabled** — Prevents stale connection reuse
- **Exponential backoff** — Retries at 100ms → 200ms → 400ms intervals
- **Synchronous fallback** — Uses `requests` when `httpx` fails
- **Graceful degradation** — Friendly error messages instead of raw stack traces

---

## 📡 API Endpoints

### Chat & AI

**`POST /v1/chat/completions`** — AI conversation gateway

- **Headers**:
  - `Authorization: Bearer <JWT>` (optional, for user_id extraction)
  - `X-User-Id: <string>` (ASCII user identifier)
  - `X-Session-Id: <string>` (session scope for history)
- **Body**:
  ```json
  {
    "messages": [{ "role": "user", "content": "Hello" }],
    "stream": false // optional, default: false
  }
  ```
- **Response**:
  ```json
  {
    "message": "...",
    "session_id": "...",
    "title": "..." // auto-generated on first turn
  }
  ```

### Session Management

**`GET /v1/sessions`** — List user sessions

- **Headers**: `Authorization` or `X-User-Id`
- **Response**:
  ```json
  {
    "sessions": [
      {
        "id": "...",
        "title": "...",
        "preview": "...",
        "message_count": 5,
        "created_at": 1234567890,
        "updated_at": 1234567890
      }
    ]
  }
  ```

**`POST /v1/sessions`** — Create new session

- **Body**: `{"title": "Optional custom title"}`
- **Response**: `{"session_id": "..."}`

**`PATCH /v1/sessions/{sid}`** — Rename session

- **Body**: `{"title": "New title"}`
- **Response**: `{"ok": true}`

**`DELETE /v1/sessions/{sid}`** — Delete session and messages

- **Response**: `{"ok": true, "deleted_messages": 10}`

**`GET /v1/sessions/{sid}/messages`** — Fetch session history

- **Query**: `?limit=100` (default: 100)
- **Response**:
  ```json
  {
    "messages": [
      {
        "role": "user",
        "content": "...",
        "timestamp": 1234567890
      }
    ]
  }
  ```

### File & Media

**`POST /v1/files/extract-docx`** — Extract text from DOCX

- **Form-data**: `file=@document.docx` (≤1MB)
- **Response**: `{"text": "..."}`

**`POST /v1/audio/transcriptions`** — Speech-to-text proxy

- **Form-data**: `file=@audio.webm`
- **Response**: `{"text": "..."}`

### System

**`GET /health`** — Health check and DB warmup

- **Response**: `{"ok": true, "db": true}`

**`GET /debug/context`** — Diagnostic endpoint (context manager state)

- **Response**: `{"pure_context": true, "memory_inline": false, ...}`

**`GET /v1/messages`** — Fetch user's global message history

- **Query**: `?limit=100`
- **Response**: `{"messages": [...]}`

---

## 🚀 Getting Started

### Prerequisites

- **Python** 3.10+ (3.11 recommended)
- **MongoDB** (optional for demo; required for production)
- **ffmpeg** (optional for audio enhancement)

### Installation

```bash
# Navigate to project directory
cd mingjing-fastapi-proxy

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Set environment variables (or create `.env` file):

```bash
# Required
export OPENAI_API_KEY=sk-...

# Optional
export OPENAI_API_BASE=https://api.openai.com/v1  # Custom gateway
export MONGODB_URI=mongodb://localhost:27017      # Database connection
export ENABLE_RATE_LIMIT=true                     # Rate limiting (default: true)
export MEMORY_RUN_INLINE=false                    # Memory mode (default: false)
export AUDIO_ENHANCE=false                        # ffmpeg preprocessing (default: false)
export FFMPEG_PATH=/usr/local/bin/ffmpeg          # Custom ffmpeg path
```

### Development Server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Access

- **API Server**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs (Swagger UI)
- **Alternative Docs**: http://localhost:8000/redoc (ReDoc)

---

## 📂 Project Structure

```
mingjing-fastapi-proxy/
├── main.py                   # API routes and application
├── core/                     # Business logic modules
│   ├── client.py             # OpenAI client with resilience
│   ├── context_manager.py    # History and context composition
│   ├── prompt_builder.py     # System prompt injection
│   └── db_mongo.py           # MongoDB operations
├── auth_routes.py            # JWT authentication endpoints
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (gitignored)
└── docs/                     # Legacy module reports (Chinese)
```

---

## 🧪 Quick Validation

### Health Check

```bash
curl http://127.0.0.1:8000/health
# Expected: {"ok": true, "db": true}
```

### DOCX Extraction

```bash
curl -F "file=@sample.docx" http://127.0.0.1:8000/v1/files/extract-docx
# Expected: {"text": "Extracted content..."}
```

### Chat Completion

```bash
curl -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-User-Id: demo-user" \
  -d '{"messages":[{"role":"user","content":"你好"}]}'
# Expected: {"message": "你好！...", "session_id": "..."}
```

### Session Creation

```bash
curl -X POST http://127.0.0.1:8000/v1/sessions \
  -H "Content-Type: application/json" \
  -H "X-User-Id: demo-user" \
  -d '{"title": "测试会话"}'
# Expected: {"session_id": "..."}
```

---

## 🔧 Configuration Reference

### Environment Variables

| Variable            | Required | Default                     | Description                                          |
| ------------------- | -------- | --------------------------- | ---------------------------------------------------- |
| `OPENAI_API_KEY`    | ✅ Yes   | -                           | OpenAI API key or compatible gateway key             |
| `OPENAI_API_BASE`   | ❌ No    | `https://api.openai.com/v1` | Custom API base URL                                  |
| `MONGODB_URI`       | ❌ No    | -                           | MongoDB connection string (required for persistence) |
| `ENABLE_RATE_LIMIT` | ❌ No    | `true`                      | Enable slowapi rate limiting                         |
| `MEMORY_RUN_INLINE` | ❌ No    | `false`                     | Run memory summarization synchronously               |
| `AUDIO_ENHANCE`     | ❌ No    | `false`                     | Enable ffmpeg audio preprocessing                    |
| `FFMPEG_PATH`       | ❌ No    | `ffmpeg`                    | Custom ffmpeg binary path                            |

### Rate Limits (per endpoint)

| Endpoint                        | Limit     | Configurable          |
| ------------------------------- | --------- | --------------------- |
| `POST /v1/chat/completions`     | 30/minute | ✅ Yes (in `main.py`) |
| `POST /v1/files/extract-docx`   | 20/minute | ✅ Yes                |
| `POST /v1/audio/transcriptions` | 10/minute | ✅ Yes                |

---

## 🌐 Deployment

### Vercel / Serverless

```bash
# Set environment variables in Vercel dashboard
OPENAI_API_KEY=sk-...
OPENAI_API_BASE=https://api.openai.com/v1
MONGODB_URI=mongodb+srv://...
MEMORY_RUN_INLINE=true       # Important for serverless
AUDIO_ENHANCE=false          # No ffmpeg in serverless

# Deploy with Vercel CLI
vercel --prod
```

**Note**: Set `MEMORY_RUN_INLINE=true` to ensure memory updates complete before response.

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENV MEMORY_RUN_INLINE=false
ENV AUDIO_ENHANCE=false

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t mingjing-backend .
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-... \
  -e MONGODB_URI=mongodb://mongo:27017 \
  mingjing-backend
```

### Traditional VPS (systemd)

```ini
# /etc/systemd/system/mingjing-backend.service
[Unit]
Description=Mingjing FastAPI Backend
After=network.target mongodb.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/mingjing-fastapi-proxy
Environment="OPENAI_API_KEY=sk-..."
Environment="MONGODB_URI=mongodb://localhost:27017"
ExecStart=/home/ubuntu/mingjing-fastapi-proxy/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable mingjing-backend
sudo systemctl start mingjing-backend
sudo systemctl status mingjing-backend
```

---

## 🔍 Debugging & Monitoring

### Check Context Manager State

```bash
curl http://127.0.0.1:8000/debug/context
# Shows PURE_CONTEXT, MEMORY_RUN_INLINE, etc.
```

### Enable Verbose Logging

```python
# In main.py, add:
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Monitor MongoDB Connections

```bash
# MongoDB shell
use mingjing_db
db.sessions.find().pretty()
db.messages.find({session_id: "..."}).pretty()
```

---

## 📚 Context Management Strategy

### Conversation Mode (Default)

- Fetches last 10 messages from session history
- Injects `PUBLIC_SYSTEM_PROMPT` for gentle guidance
- Includes user message + history in prompt

### Document Analysis Mode

- Triggered when user message contains `===== 文本开始 =====` markers
- Switches to `DOC_ANALYSIS_SYSTEM_PROMPT`
- **Trims all history** to focus on document content only
- System prompt emphasizes objective, structured summarization

### Memory Summarization (Optional)

- Triggered after N turns (configurable)
- Summarizes conversation into key points
- Prepends summary to future context
- Runs async (background task) or inline (serverless)

---

## 🤝 Contributing

This backend follows intentional design constraints:

1. **Network resilience first**: Optimize for flaky connections
2. **Graceful degradation**: Friendly errors over stack traces
3. **Serverless-compatible**: Support both async and inline modes
4. **Rate limit awareness**: Prevent abuse while maintaining UX
5. **Chinese user focus**: Error messages and prompts in Chinese

---

## 📄 License

Proprietary. For evaluation and demonstration purposes.

---

## 📖 Additional Documentation

Legacy module
