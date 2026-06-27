import time
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from loguru import logger

from src.api.middleware import RequestIDMiddleware, setup_logger
from src.database.db_manager import db
from src.agent.reviewer_graph import build_review_graph

# 初始化日志
setup_logger()

# 创建 FastAPI 实例
app = FastAPI(title="Code Review Agent API", version="2.0.0")

# 挂载中间件
app.add_middleware(RequestIDMiddleware)

# 构建全局的 LangGraph 图
graph = build_review_graph()

# --- 核心请求模型 ---
class ReviewRequest(BaseModel):
    filename: str
    code: str

# --- 核心后台任务 ---
def background_review_task(review_id: str, request_id: str, filename: str, code: str):
    """
    后台执行 LangGraph 并将结果持久化到 SQLite 中
    """
    from src.api.middleware import request_id_context
    # 恢复 contextvar
    request_id_context.set(request_id)
    
    logger.info(f"Starting background review task for review_id: {review_id}")
    
    initial_state = {
        "code": code,
        "filename": filename,
        "metrics": {"workflow_start_time": time.time()}
    }
    
    try:
        # 执行图
        final_state = graph.invoke(initial_state)
        metrics = final_state.get("metrics", {})
        
        # 1. 记录各个 Agent 的运行情况
        # 安全性审查
        db.add_agent_run(
            review_id=review_id,
            agent_name="security_reviewer",
            status="success",
            latency_ms=int(metrics.get("security_reviewer_time", 0) * 1000),
            token_input=metrics.get("security_tokens_in"),
            token_output=metrics.get("security_tokens_out"),
            result=final_state.get("security_report")
        )
        # 质量审查
        db.add_agent_run(
            review_id=review_id,
            agent_name="quality_reviewer",
            status="success",
            latency_ms=int(metrics.get("quality_reviewer_time", 0) * 1000),
            token_input=metrics.get("quality_tokens_in"),
            token_output=metrics.get("quality_tokens_out"),
            result=final_state.get("quality_report")
        )
        # 性能审查
        db.add_agent_run(
            review_id=review_id,
            agent_name="performance_reviewer",
            status="success",
            latency_ms=int(metrics.get("performance_reviewer_time", 0) * 1000),
            token_input=metrics.get("performance_tokens_in"),
            token_output=metrics.get("performance_tokens_out"),
            result=final_state.get("performance_report")
        )
        
        # 2. 更新主报告状态
        total_latency_ms = int(metrics.get("total_workflow_time", 0) * 1000)
        updates = {
            "status": "completed",
            "report": final_state.get("final_report"),
            "total_latency_ms": total_latency_ms,
            # 可以通过某种方式提取，这里暂且 hardcode 供演示
            "score": 85, 
            "risk_level": "medium"
        }
        db.update_review(review_id, updates)
        
        logger.info(f"Background review task completed for review_id: {review_id}")
        
    except Exception as e:
        logger.exception(f"Error in background review task for review_id: {review_id}")
        db.update_review(review_id, {"status": "failed", "report": str(e)})

# --- 路由 ---
@app.get("/api/v1/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy"}

@app.post("/api/v1/review")
async def start_review(req: ReviewRequest, background_tasks: BackgroundTasks):
    """
    提交代码审查任务（异步），返回唯一的 review_id
    """
    from src.api.middleware import request_id_context
    current_request_id = request_id_context.get()
    
    logger.info(f"Received review request for filename: {req.filename}")
    
    # 在数据库中创建 pending 状态的记录
    review_id = db.create_review(req.filename, req.code)
    
    # 派发后台任务 (显式传入 request_id)
    background_tasks.add_task(background_review_task, review_id, current_request_id, req.filename, req.code)
    
    return {"review_id": review_id, "status": "pending", "message": "Review task is running in the background."}

@app.get("/api/v1/review/{review_id}")
async def get_review(review_id: str):
    """
    获取单个审查报告及其相关的 metrics
    """
    review = db.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review

@app.get("/api/v1/review/{review_id}/status")
async def get_review_status(review_id: str):
    """
    获取单个审查报告的轻量级状态（用于前端轮询）
    """
    review = db.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    return {
        "review_id": review["id"],
        "status": review["status"],
        "score": review.get("score"),
        "risk_level": review.get("risk_level"),
        "total_latency_ms": review.get("total_latency_ms")
    }

@app.get("/api/v1/history")
async def get_history(limit: int = 50, offset: int = 0):
    """
    获取历史记录
    """
    history = db.get_history(limit=limit, offset=offset)
    return {"history": history}

# 挂载静态文件目录 (必须放在所有 API 路由之后，以免覆盖 /api)
from fastapi.staticfiles import StaticFiles
import os

static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
