# Agentic Code Review System 🚀

A production-grade, asynchronous multi-agent code review system powered by LangGraph, FastAPI, and LLMs. This system analyzes source code for security vulnerabilities, code quality issues, and performance bottlenecks, synthesizing a comprehensive Markdown report.

![System Health](https://img.shields.io/badge/System-Healthy-brightgreen)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688?logo=fastapi)
![LangGraph](https://img.shields.io/badge/LangGraph-0.0.65-blue)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)

## 🌟 Key Features

- **Multi-Agent Architecture**: Utilizes LangGraph to orchestrate specialized LLM agents (Security, Quality, Performance) working in parallel.
- **Asynchronous Task Processing**: Employs FastAPI `BackgroundTasks` for non-blocking execution of long-running LLM inferences, with robust status polling.
- **LLM Provider Agnostic**: Seamlessly switch between DeepSeek, OpenAI, Claude, Ollama, and Mock providers directly from the UI.
- **Persistent Audit Logging**: SQLite database backed by Docker volumes ensures every review request, latency metric, and LLM token usage is recorded.
- **Modern Glassmorphism UI**: A sleek, dark-themed vanilla JS frontend for real-time monitoring and reporting.

---

## 🏛️ System Architecture

```mermaid
graph TD
    subgraph Frontend [Modern Web Console]
        UI[Vanilla JS App]
        Poll[Status Polling 1.5s]
    end

    subgraph Backend [FastAPI Application]
        API[API Endpoints]
        TaskQueue[Background Tasks]
        DB[(SQLite Database)]
    end

    subgraph LangGraph Orchestration [Multi-Agent Pipeline]
        Router{Router Node}
        Security[Security Agent]
        Quality[Quality Agent]
        Performance[Performance Agent]
        Synthesizer[Synthesizer Node]
    end

    subgraph LLM Providers
        OpenAI[OpenAI]
        DeepSeek[DeepSeek]
        Ollama[Local Ollama]
    end

    UI -- "1. POST /api/v1/review" --> API
    API -- "2. Returns review_id" --> UI
    API -- "3. Dispatches async task" --> TaskQueue
    TaskQueue -- "4. Triggers Graph" --> Router
    
    Router --> Security
    Router --> Quality
    Router --> Performance
    
    Security --> Synthesizer
    Quality --> Synthesizer
    Performance --> Synthesizer

    Security -.-> LLM Providers
    Quality -.-> LLM Providers
    Performance -.-> LLM Providers

    Synthesizer -- "5. Updates Status & Report" --> DB
    Poll -- "6. GET /api/v1/review/{id}/status" --> API
    API -- "Reads from" --> DB
```

---

## 🚀 Quickstart

### Option 1: Docker (Recommended)

The easiest way to run the application with full persistence.

```bash
# Clone the repository
git clone https://github.com/yourusername/code-review-agent.git
cd code-review-agent

# Build and start the container
docker-compose up --build -d
```
Access the web console at: `http://localhost:7861`

### Option 2: Local Development

```bash
# Create a virtual environment
python -m venv .venv

# Windows
.\.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the server
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 7861
```

---

## 📡 API Reference

### `POST /api/v1/review`
Submits code for review.
```json
{
  "filename": "auth.py",
  "code": "def login(user, pw):\n  execute(f'SELECT * FROM users WHERE pass={pw}')",
  "provider": "DeepSeek",
  "api_key": "sk-...",
  "model_name": "deepseek-chat"
}
```
**Response**: `{"review_id": "uuid"}`

### `GET /api/v1/review/{review_id}/status`
Polls the execution status (`pending`, `running`, `completed`, `failed`).

### `GET /api/v1/review/{review_id}`
Retrieves the completed review report, risk level, score, and detailed agent latency/token metrics.

### `GET /api/v1/history`
Fetches a chronological log of all historical code reviews.

---

## 🛠️ Tech Stack
- **Backend Framework**: FastAPI, Pydantic, Uvicorn
- **AI Orchestration**: LangChain, LangGraph
- **Database**: SQLite (built-in)
- **Frontend**: HTML5, Vanilla CSS (Glassmorphism), Vanilla JS
- **Deployment**: Docker, Docker Compose
