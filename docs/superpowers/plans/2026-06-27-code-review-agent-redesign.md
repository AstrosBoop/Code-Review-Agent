# Enterprise Code-Review-Agent Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the single-agent Gradio prototype into an enterprise-grade multi-agent Code-Review system featuring FastAPI, LangGraph parallel orchestration, SQLite persistence (two tables), JSON structured logging with request ID tracking, and offline embedding Docker image.

**Architecture:** A FastAPI service handles incoming review requests, generates a request-specific UUID via context middleware, and executes a LangGraph state graph. The graph pre-runs local AST/regex detectors, queries standard coding guidelines using local SentenceTransformer/FAISS RAG, forks into three parallel LLM reviewer agents (security, quality, performance), aggregates their reports, and writes all records (reviews and agent run metrics) to SQLite.

**Tech Stack:** FastAPI, Uvicorn, LangGraph, Loguru, SentenceTransformer, FAISS, SQLite, Docker, Docker Compose

---

## 🚦 Execution Constraints & Guidelines

1. **Sequential Task Execution**: Tasks must be implemented in order: Task 1 -> Task 2 -> Task 3 -> Task 4 -> Task 5 -> Task 6 -> Task 7. Only dispatch a single subagent for one task at a time; do not run parallel changes on core files.
2. **Task Verification**: Run unit tests or verify manually after completing each task before proceeding to the next.
3. **Commit after each task**: Commit files with clear, descriptive messages once a task's verification passes.
4. **Post-Task Report**: After completing each task, output a brief summary specifying:
   - Modified/created files.
   - Core implementation logic.
   - How it was verified.
   - Any identified risks or dependencies.
5. **Manual Review Checkpoints**: Pause and request manual user review after the completion of:
   - **Task 2 (Database Initialization)**
   - **Task 3 (Logging & Middleware)**
   - **Task 5 (FastAPI & DB Integration)**
   - **Task 7 (Docker Build & E2E Testing)**
6. **E2E Verification**: In the final step, run a full E2E test verifying:
   - `POST /api/v1/review`
   - `GET /api/v1/history`
   - `GET /api/v1/history/{id}`
   - `docker-compose up`

---

### Task 1: Environment & Dependency Configuration

**Files:**
- Modify: `requirements.txt`
- Test: Verify package installation

- [ ] **Step 1: Update requirements.txt with new dependencies**
Add the necessary packages to `requirements.txt`.
```text
fastapi>=0.100.0
uvicorn>=0.22.0
langgraph>=0.0.10
loguru>=0.7.0
sentence-transformers>=2.2.2
faiss-cpu>=1.7.4
pydantic>=2.0
numpy>=1.24.0
jinja2>=3.1.2
openai>=1.0.0
```

- [ ] **Step 2: Run installation to verify compatibility**
Run command:
`pip install -r requirements.txt`
Expected: All packages installed successfully.

- [ ] **Step 3: Commit environment configuration**
```bash
git add requirements.txt
git commit -m "chore: configure project dependencies for FastAPI, LangGraph and Loguru"
```

---

### Task 2: Database Initialization (SQLite)

**Files:**
- Create: `src/database/db_manager.py`
- Test: `tests/test_database.py`

- [ ] **Step 1: Write the database manager module**
Create `src/database/db_manager.py` with standard SQLite tables initialization.
```python
import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "reviews.db"

def get_db_connection():
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create reviews table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id TEXT PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        filename TEXT,
        code_snippet TEXT,
        score INTEGER,
        risk_level TEXT,
        report TEXT,
        status TEXT,
        total_latency_ms INTEGER
    );
    """)
    
    # Create agent_runs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agent_runs (
        id TEXT PRIMARY KEY,
        review_id TEXT,
        agent_name TEXT,
        status TEXT,
        latency_ms INTEGER,
        token_input INTEGER,
        token_output INTEGER,
        result TEXT,
        error_message TEXT,
        FOREIGN KEY (review_id) REFERENCES reviews (id)
    );
    """)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
```

- [ ] **Step 2: Create a unit test for database manager**
Create `tests/test_database.py` to verify connection and table schema creation.
```python
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

import unittest
import tempfile
import os
from database import db_manager

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        db_manager.DB_PATH = Path(self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_init_db(self):
        db_manager.init_db()
        conn = db_manager.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        self.assertIn("reviews", tables)
        self.assertIn("agent_runs", tables)
        conn.close()

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the database test**
Run command:
`python tests/test_database.py`
Expected: Test passes successfully.

- [ ] **Step 4: Commit database manager**
```bash
git add src/database/db_manager.py tests/test_database.py
git commit -m "feat: implement SQLite database manager with reviews and agent_runs schemas"
```

---

### Task 3: Structured Logging & Request ID Middleware

**Files:**
- Create: `src/api/middleware.py`
- Test: Verify request tracing in logs

- [ ] **Step 1: Write Request ID middleware and logger configuration**
Create `src/api/middleware.py` using `contextvars` to manage request IDs and format JSON logs.
```python
import uuid
import time
from contextvars import ContextVar
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger
import sys

# Context variable to hold request_id for the current thread/task
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

def configure_logging(log_file_path: str = "logs/app.log"):
    logger.remove()
    
    # Custom format showing the request_id
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "ID: <cyan>{extra[request_id]}</cyan> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    
    # Console output
    logger.add(
        sys.stdout,
        format=log_format,
        level="DEBUG",
        filter=lambda record: record["extra"].setdefault("request_id", request_id_ctx.get()) or True
    )
    
    # JSON file output for log aggregation
    logger.add(
        log_file_path,
        serialize=True,
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
        filter=lambda record: record["extra"].setdefault("request_id", request_id_ctx.get()) or True
    )

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx.set(req_id)
        
        # Log incoming request
        logger.info(f"Incoming request: {request.method} {request.url.path}")
        
        start_time = time.time()
        response = await call_next(request)
        duration_ms = int((time.time() - start_time) * 1000)
        
        response.headers["X-Request-ID"] = req_id
        logger.info(f"Finished request: {request.method} {request.url.path} - Status: {response.status_code} - Latency: {duration_ms}ms")
        
        request_id_ctx.reset(token)
        return response
```

- [ ] **Step 2: Commit Logging and Middleware module**
```bash
git add src/api/middleware.py
git commit -m "feat: implement JSON structured logging and Request ID context middleware"
```

---

### Task 4: LangGraph Multi-Agent Workflow

**Files:**
- Create: `src/agent/reviewer_graph.py`
- Test: `tests/test_reviewer_graph.py`

- [ ] **Step 1: Write the LangGraph workflow engine**
Create `src/agent/reviewer_graph.py` defining nodes, state and transition topology.
```python
import os
import json
import time
import uuid
from typing import TypedDict, Dict, Any, List
from openai import OpenAI
from loguru import logger
from langgraph.graph import StateGraph, END

from tools.optimizer import suggest_optimizations

class ReviewState(TypedDict):
    id: str
    code: str
    filename: str
    static_results: Dict[str, Any]
    rag_context: str
    security_report: str
    quality_report: str
    performance_report: str
    final_report: str
    # Avoid merge conflicts in parallel execution by using distinct metric fields
    static_latency_ms: int
    security_metrics: Dict[str, Any]
    quality_metrics: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    synthesizer_metrics: Dict[str, Any]

def _call_llm(system_prompt: str, user_content: str, provider: str = "deepseek") -> tuple[str, dict]:
    provider = provider.lower()
    start_time = time.time()
    
    # 1. Claude Anthropic Provider
    if provider == "claude":
        from anthropic import Anthropic
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            temperature=0.2,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}]
        )
        latency_ms = int((time.time() - start_time) * 1000)
        tokens = {
            "input": response.usage.input_tokens,
            "output": response.usage.output_tokens
        }
        return response.content[0].text, {"latency_ms": latency_ms, "tokens": tokens}
        
    # 2. OpenAI / OpenAI-compatible Providers (DeepSeek, Gemini, Ollama)
    configs = {
        "deepseek": {
            "base_url": "https://api.deepseek.com/v1",
            "key_env": "DEEPSEEK_API_KEY",
            "model": "deepseek-chat"
        },
        "openai": {
            "base_url": None,
            "key_env": "OPENAI_API_KEY",
            "model": "gpt-4o-mini"
        },
        "gemini": {
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
            "key_env": "GEMINI_API_KEY",
            "model": "gemini-2.5-flash"
        },
        "ollama": {
            "base_url": "http://localhost:11434/v1",
            "key_env": "OLLAMA_API_KEY",
            "model": "qwen2.5-coder:7b"
        }
    }
    
    cfg = configs.get(provider, configs["deepseek"])
    api_key = os.getenv(cfg["key_env"]) if cfg["key_env"] else "dummy_key"
    if provider == "ollama":
        api_key = "ollama"
        
    client = OpenAI(api_key=api_key, base_url=cfg["base_url"])
    response = client.chat.completions.create(
        model=cfg["model"],
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        max_tokens=2048,
        temperature=0.2
    )
    latency_ms = int((time.time() - start_time) * 1000)
    tokens = {
        "input": response.usage.prompt_tokens,
        "output": response.usage.completion_tokens
    }
    return response.choices[0].message.content, {"latency_ms": latency_ms, "tokens": tokens}

# --- Nodes ---

def run_static_tools_node(state: ReviewState) -> Dict[str, Any]:
    logger.debug("Executing static code checkers (AST, RegEx rules).")
    start = time.time()
    
    quality = analyze_code_quality(state["code"])
    security = check_security(state["code"])
    opt = suggest_optimizations(state["code"])
    
    latency = int((time.time() - start) * 1000)
    logger.info(f"Static tools completed in {latency}ms")
    
    return {
        "static_results": {
            "quality": quality,
            "security": security,
            "optimization": opt
        },
        "static_latency_ms": latency
    }

def retrieve_rag_node(state: ReviewState) -> Dict[str, Any]:
    logger.debug("Retrieving coding standards from RAG Vector DB.")
    keywords = []
    sec_issues = state["static_results"]["security"].get("vulnerabilities", [])
    for v in sec_issues:
        keywords.append(v.get("id"))
    
    qual_issues = state["static_results"]["quality"].get("issues", [])
    for q in qual_issues:
        keywords.append(q.get("type"))
        
    query = " ".join(filter(None, keywords)) or "代码规范 最佳实践"
    
    # Retrieve from RAG (lazy-load database to prevent overhead)
    from rag.knowledge_base import CodeKnowledgeBase
    from pathlib import Path
    kb = CodeKnowledgeBase(lazy_load=True)
    # Correct resolution path to parent directory: d:\AI Coding\Code-Review-Agent\data\processed\vector_db
    kb.load(str(Path(__file__).resolve().parents[2] / "data" / "processed" / "vector_db"))
    
    from sentence_transformers import SentenceTransformer
    kb.encoder = SentenceTransformer(kb.embedding_model, local_files_only=True)
    results = kb.retrieve(query, top_k=3)
    
    rag_context = "\n".join([
        f"- {r['document']['info']['title']}: {r['document']['info']['content']}"
        for r in results
    ])
    
    logger.info(f"Retrieved {len(results)} RAG context items.")
    return {"rag_context": rag_context}

def security_reviewer_node(state: ReviewState) -> Dict[str, Any]:
    logger.info("Starting security reviewer Agent node.")
    prompt = (
        "你是一个网络安全与代码安全审计专家。请根据以下信息对代码进行安全审查：\n"
        "1. 原始代码。\n"
        "2. 静态工具初步扫描出的安全漏洞风险列表。\n"
        "3. RAG 知识库检索出的安全编码规范。\n\n"
        "请输出一份【安全审查子报告】，包含：\n"
        "- 是否发现安全漏洞，漏洞危险等级（High/Medium/Low）。\n"
        "- 对静态工具发现的问题进行深度剖析（确认是真实漏洞还是误报），并指出具体行数。\n"
        "- 给出具体的修复代码示例。\n"
        "- 若无漏洞，明确说明'未检测到明显的安全风险'。\n"
        "仅关注安全，忽略命名规范和格式。"
    )
    user_content = (
        f"代码：\n```\n{state['code']}\n```\n\n"
        f"静态检查结果：\n{json.dumps(state['static_results']['security'], ensure_ascii=False)}\n\n"
        f"RAG 规范：\n{state['rag_context']}"
    )
    
    report, meta = _call_llm(prompt, user_content)
    logger.info(f"Security reviewer Agent finished in {meta['latency_ms']}ms.")
    return {
        "security_report": report,
        "security_metrics": meta
    }

def quality_reviewer_node(state: ReviewState) -> Dict[str, Any]:
    logger.info("Starting quality reviewer Agent node.")
    prompt = (
        "你是一个代码重构与整洁代码（Clean Code）专家。请根据以下信息对代码进行质量审查：\n"
        "1. 原始代码。\n"
        "2. AST 静态分析工具检测到的函数长度、参数个数、命名不规范、魔法数字、注释率等问题。\n"
        "3. RAG 知识库中关于代码结构与设计原则的规范。\n\n"
        "请输出一份【代码质量子报告】，包含：\n"
        "- 针对命名风格、函数复杂度和嵌套过深等重构建议。\n"
        "- 评估可读性与注释合理性。\n"
        "仅关注代码结构和规范，忽略安全漏洞和运行效率。"
    )
    user_content = (
        f"代码：\n```\n{state['code']}\n```\n\n"
        f"静态检查结果：\n{json.dumps(state['static_results']['quality'], ensure_ascii=False)}\n\n"
        f"RAG 规范：\n{state['rag_context']}"
    )
    
    report, meta = _call_llm(prompt, user_content)
    logger.info(f"Quality reviewer Agent finished in {meta['latency_ms']}ms.")
    return {
        "quality_report": report,
        "quality_metrics": meta
    }

def performance_reviewer_node(state: ReviewState) -> Dict[str, Any]:
    logger.info("Starting performance reviewer Agent node.")
    prompt = (
        "你是一个资深的系统性能调优与算法专家。请根据以下信息对代码进行性能审查：\n"
        "1. 原始代码。\n"
        "2. 静态分析工具指出的性能瓶颈。\n"
        "3. RAG 知识库中关于运行效率的指南。\n\n"
        "请输出一份【性能优化子报告】，包含：\n"
        "- 分析时间/空间复杂度瓶颈。\n"
        "- 给出列表推导式、字符串拼接、重复计算等具体的优化建议。\n"
        "- 给出优化前后的对比代码片段。\n"
        "仅关注效率，忽略安全和规范。"
    )
    user_content = (
        f"代码：\n```\n{state['code']}\n```\n\n"
        f"静态检查结果：\n{json.dumps(state['static_results']['optimization'], ensure_ascii=False)}\n\n"
        f"RAG 规范：\n{state['rag_context']}"
    )
    
    report, meta = _call_llm(prompt, user_content)
    logger.info(f"Performance reviewer Agent finished in {meta['latency_ms']}ms.")
    return {
        "performance_report": report,
        "performance_metrics": meta
    }

def synthesizer_node(state: ReviewState) -> Dict[str, Any]:
    logger.info("Starting synthesizer Agent node.")
    prompt = (
        "你是一个资深的技术专家和团队 Lead。你的任务是将【安全审查子报告】、【代码质量子报告】和【性能优化子报告】融合成一份最终的中文代码审查报告。\n\n"
        "你需要做到：\n"
        "1. 消除冗余，用专业一致的中文语气整合成文。\n"
        "2. 计算一个综合评分（满分 100 分），综合考虑安全（权重最大）、质量与性能。\n"
        "3. 严格遵循以下 Markdown 结构输出：\n"
        "   # 🤖 智能代码审查报告\n\n"
        "   ## 一、 总体评估\n"
        "   - **总体评分**：[分数]/100\n"
        "   - **风险等级**：[高/中/低]\n"
        "   - **核心改进意见**：[总结]\n\n"
        "   ## 二、 安全漏洞\n"
        "   [安全分析]\n\n"
        "   ## 三、 代码质量与规范\n"
        "   [质量分析]\n\n"
        "   ## 四、 性能优化建议\n"
        "   [性能分析]\n\n"
        "   ## 五、 改进与建议总结\n"
        "   [提供重构后的完整参考代码]\n"
    )
    user_content = (
        f"安全报告：\n{state['security_report']}\n\n"
        f"质量报告：\n{state['quality_report']}\n\n"
        f"性能报告：\n{state['performance_report']}"
    )
    
    report, meta = _call_llm(prompt, user_content)
    logger.info("Final review report synthesis complete.")
    return {
        "final_report": report,
        "synthesizer_metrics": meta
    }

# --- Compile Graph ---

def build_reviewer_graph():
    builder = StateGraph(ReviewState)
    
    # Add nodes
    builder.add_node("run_static_tools", run_static_tools_node)
    builder.add_node("retrieve_rag", retrieve_rag_node)
    builder.add_node("security_reviewer", security_reviewer_node)
    builder.add_node("quality_reviewer", quality_reviewer_node)
    builder.add_node("performance_reviewer", performance_reviewer_node)
    builder.add_node("synthesizer", synthesizer_node)
    
    # Connect edges
    builder.set_entry_point("run_static_tools")
    builder.add_edge("run_static_tools", "retrieve_rag")
    
    # Broadcast parallel nodes
    builder.add_edge("retrieve_rag", "security_reviewer")
    builder.add_edge("retrieve_rag", "quality_reviewer")
    builder.add_edge("retrieve_rag", "performance_reviewer")
    
    # Gather nodes
    builder.add_edge("security_reviewer", "synthesizer")
    builder.add_edge("quality_reviewer", "synthesizer")
    builder.add_edge("performance_reviewer", "synthesizer")
    
    builder.add_edge("synthesizer", END)
    
    return builder.compile()
```

- [ ] **Step 2: Commit LangGraph Reviewer module**
```bash
git add src/agent/reviewer_graph.py
git commit -m "feat: implement LangGraph state graph with parallel specialized agent nodes"
```

---

### Task 5: FastAPI Application & DB Persistence

**Files:**
- Create: `src/api/app.py`
- Test: Verify endpoint requests locally

- [ ] **Step 1: Write the main FastAPI application**
Create `src/api/app.py` linking routing, database persistence and execution log mapping.
```python
import os
import sys
import time
import re
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from loguru import logger

# Append paths
sys.path.append(str(Path(__file__).parent.parent))

from api.middleware import RequestIDMiddleware, configure_logging, request_id_ctx
from database.db_manager import get_db_connection, init_db
from agent.reviewer_graph import build_reviewer_graph

# Setup Logging
configure_logging()
init_db()

app = FastAPI(title="Code-Review-Agent API", version="1.0.0")
app.add_middleware(RequestIDMiddleware)

# Mount static files folder
STATIC_DIR = Path(__file__).parent.parent.parent / "static"
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

graph = build_reviewer_graph()

class CodeReviewRequest(BaseModel):
    code: str
    filename: str = "app.py"

def _extract_score_and_risk(report: str) -> tuple[int, str]:
    # Extract score (e.g. 85/100 or 85)
    score_match = re.search(r"评分[**：:\s]*(\d+)", report)
    score = int(score_match.group(1)) if score_match else 80
    
    # Extract risk level (高/中/低 or high/medium/low)
    risk = "low"
    if "高" in report or "High" in report or "high" in report:
        risk = "high"
    elif "中" in report or "Medium" in report or "medium" in report:
        risk = "medium"
    return score, risk

@app.post("/api/v1/review")
async def review_code(payload: CodeReviewRequest):
    req_id = request_id_ctx.get()
    logger.info(f"Starting review pipeline for file: {payload.filename}")
    
    start_time = time.time()
    try:
        initial_state = {
            "id": req_id,
            "code": payload.code,
            "filename": payload.filename,
            "static_results": {},
            "rag_context": "",
            "security_report": "",
            "quality_report": "",
            "performance_report": "",
            "final_report": "",
            "static_latency_ms": 0,
            "security_metrics": {},
            "quality_metrics": {},
            "performance_metrics": {},
            "synthesizer_metrics": {}
        }
        
        # Execute LangGraph review workflow
        result = graph.invoke(initial_state)
        total_latency = int((time.time() - start_time) * 1000)
        
        score, risk = _extract_score_and_risk(result["final_report"])
        
        # Write to reviews table in SQLite
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO reviews (id, filename, code_snippet, score, risk_level, report, status, total_latency_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            req_id,
            payload.filename,
            payload.code[:200], # Store snippet
            score,
            risk,
            result["final_report"],
            "completed",
            total_latency
        ))
        
        # Write agent run details to agent_runs table
        agents = ["security", "quality", "performance"]
        for agent in agents:
            meta = result.get(f"{agent}_metrics", {})
            tokens = meta.get("tokens", {})
            cursor.execute("""
            INSERT INTO agent_runs (id, review_id, agent_name, status, latency_ms, token_input, token_output, result, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                f"{req_id}-{agent}",
                req_id,
                agent,
                "completed",
                meta.get("latency_ms", 0),
                tokens.get("input", 0),
                tokens.get("output", 0),
                result.get(f"{agent}_report", ""),
                None
            ))
            
        conn.commit()
        conn.close()
        
        logger.info(f"Successfully processed and stored review {req_id} with score {score}")
        
        return {
            "review_id": req_id,
            "score": score,
            "risk_level": risk,
            "report": result["final_report"],
            "total_latency_ms": total_latency
        }
        
    except Exception as e:
        total_latency = int((time.time() - start_time) * 1000)
        logger.exception("Error executing review pipeline.")
        
        # Store failure state in SQLite
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO reviews (id, filename, code_snippet, score, risk_level, report, status, total_latency_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (req_id, payload.filename, payload.code[:200], 0, "unknown", f"Review failed: {str(e)}", "failed", total_latency))
        conn.commit()
        conn.close()
        
        raise HTTPException(status_code=500, detail=f"Review execution failed: {str(e)}")

@app.get("/api/v1/history")
async def get_history():
    logger.info("Fetching review history list.")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, created_at, filename, score, risk_level, status, total_latency_ms 
    FROM reviews 
    ORDER BY created_at DESC;
    """)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

@app.get("/api/v1/history/{review_id}")
async def get_review_detail(review_id: str):
    logger.info(f"Fetching review details for ID: {review_id}")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM reviews WHERE id = ?;", (review_id,))
    review = cursor.fetchone()
    
    if not review:
        conn.close()
        raise HTTPException(status_code=404, detail="Review record not found.")
        
    cursor.execute("SELECT agent_name, status, latency_ms, token_input, token_output, error_message FROM agent_runs WHERE review_id = ?;", (review_id,))
    runs = cursor.fetchall()
    conn.close()
    
    result = dict(review)
    result["agent_runs"] = [dict(run) for run in runs]
    return result

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return "<h3>Index page not found. Please build Task 6.</h3>"
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()
```

- [ ] **Step 2: Commit FastAPI application**
```bash
git add src/api/app.py
git commit -m "feat: implement FastAPI server with API endpoints and SQLite persistence"
```

---

### Task 6: Modern UI Frontend (HTML/CSS/JS)

**Files:**
- Create: `static/index.html`
- Test: Verify local server rendering

- [ ] **Step 1: Write a premium UI page using vanilla CSS & JS**
Create `static/index.html` with a clean glassmorphism dark theme.
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🤖 智能代码审查 Agent 平台</title>
    <style>
        :root {
            --bg-color: #0b0f19;
            --card-bg: rgba(22, 30, 49, 0.7);
            --primary: #4f46e5;
            --primary-hover: #6366f1;
            --text-color: #f3f4f6;
            --text-muted: #9ca3af;
            --border-color: rgba(255, 255, 255, 0.08);
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
            padding: 2rem;
        }
        .container { max-width: 1200px; margin: 0 auto; display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; }
        header { text-align: center; grid-column: span 2; margin-bottom: 2rem; }
        header h1 { font-size: 2.5rem; color: #fff; margin-bottom: 0.5rem; }
        header p { color: var(--text-muted); }
        .panel {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.5rem;
            backdrop-filter: blur(12px);
        }
        textarea {
            width: 100%; height: 400px;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: #10b981;
            font-family: "Courier New", Courier, monospace;
            padding: 1rem; font-size: 1rem; resize: none; margin-bottom: 1rem;
        }
        button {
            width: 100%; padding: 0.8rem; background: var(--primary);
            color: #fff; border: none; border-radius: 8px; cursor: pointer;
            font-size: 1.1rem; font-weight: bold; transition: 0.2s;
        }
        button:hover { background: var(--primary-hover); }
        .report-box {
            background: rgba(0, 0, 0, 0.2);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1rem;
            height: 480px;
            overflow-y: auto;
            font-size: 0.95rem;
        }
        .meta-info {
            margin-top: 1rem; display: flex; justify-content: space-between;
            background: rgba(255, 255, 255, 0.05); padding: 0.8rem; border-radius: 8px;
        }
        h2 { margin-bottom: 1rem; font-size: 1.4rem; }
        .badge { padding: 0.2rem 0.6rem; border-radius: 4px; font-weight: bold; }
        .badge-high { background: var(--danger); }
        .badge-medium { background: var(--warning); }
        .badge-low { background: var(--success); }
    </style>
</head>
<body>
    <header>
        <h1>🤖 智能代码审查 Agent 平台</h1>
        <p>基于 FastAPI + LangGraph + RAG + Docker 容器化的企业级代码审查助手</p>
    </header>
    <div class="container">
        <div class="panel">
            <h2>💻 输入代码</h2>
            <textarea id="code-input">import sqlite3
import hashlib

password = "admin123"
db_conn = sqlite3.connect("users.db")

def get_user(username):
    cursor = db_conn.cursor()
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    cursor.execute(query)
    return cursor.fetchone()

def hash_password(pwd):
    return hashlib.md5(pwd.encode()).hexdigest()
            </textarea>
            <button id="submit-btn" onclick="submitReview()">提交审查</button>
        </div>
        <div class="panel">
            <h2>📄 审查报告</h2>
            <div id="report-view" class="report-box">
                期待您的代码提交...报告将在此处以 Markdown 渲染展现。
            </div>
            <div class="meta-info" id="meta-view" style="display:none;">
                <div>综合评分: <span id="score-val" class="badge">--</span></div>
                <div>安全等级: <span id="risk-val" class="badge">--</span></div>
                <div>耗时: <span id="latency-val">--</span> ms</div>
            </div>
        </div>
    </div>
    <script>
        async function submitReview() {
            const btn = document.getElementById("submit-btn");
            const code = document.getElementById("code-input").value;
            const reportView = document.getElementById("report-view");
            const metaView = document.getElementById("meta-view");
            
            btn.disabled = true;
            btn.innerText = "审查中，请稍候...";
            reportView.innerHTML = "<h4>Agent 正在执行并行审查拓扑流程，请稍候...</h4>";
            metaView.style.display = "none";
            
            try {
                const res = await fetch("/api/v1/review", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ code: code, filename: "test_code.py" })
                });
                if (!res.ok) throw new Error(await res.text());
                const data = await res.json();
                
                // Simple parser replacement for markdown codeblocks to HTML
                let formatted = data.report
                    .replace(/#(?!#)\s*(.*)/g, '<h1>$1</h1>')
                    .replace(/##\s*(.*)/g, '<h2>$1</h2>')
                    .replace(/###\s*(.*)/g, '<h3>$1</h3>')
                    .replace(/\n/g, '<br>');
                
                reportView.innerHTML = formatted;
                
                // Set Badge Colors
                const scoreSpan = document.getElementById("score-val");
                scoreSpan.innerText = data.score;
                scoreSpan.className = "badge " + (data.score >= 80 ? "badge-low" : data.score >= 60 ? "badge-medium" : "badge-high");
                
                const riskSpan = document.getElementById("risk-val");
                riskSpan.innerText = data.risk_level.toUpperCase();
                riskSpan.className = "badge " + (data.risk_level === "high" ? "badge-high" : data.risk_level === "medium" ? "badge-medium" : "badge-low");
                
                document.getElementById("latency-val").innerText = data.total_latency_ms;
                metaView.style.display = "flex";
                
            } catch (err) {
                reportView.innerHTML = `<h4 style="color:var(--danger)">审查失败</h4><p>${err.message}</p>`;
            } finally {
                btn.disabled = false;
                btn.innerText = "提交审查";
            }
        }
    </script>
</body>
</html>
```

- [ ] **Step 2: Commit HTML Frontend**
```bash
git add static/index.html
git commit -m "feat: implement visual glassmorphism dark-theme HTML frontend"
```

---

### Task 7: Containerization & Compose Config (Docker)

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Test: Build container and run verification

- [ ] **Step 1: Create Dockerfile**
Create `Dockerfile` baking local `SentenceTransformer` during building.
```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install git for downloads if needed
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download SentenceTransformer model to local cache during Docker build
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY . .

# Run api server
EXPOSE 7861

# Set Hugging Face offline variables
ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "7861"]
```

- [ ] **Step 2: Create docker-compose.yml**
Create `docker-compose.yml` configuration mapping files, directories and secrets.
```yaml
version: '3.8'

services:
  code-review-agent:
    build: .
    container_name: code-review-agent-service
    ports:
      - "7861:7861"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    restart: always
```

- [ ] **Step 3: Commit Container configuration files**
```bash
git add Dockerfile docker-compose.yml
git commit -m "deploy: add Dockerfile and docker-compose configurations for containerized deployment"
```
