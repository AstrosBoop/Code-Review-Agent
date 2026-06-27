import uuid
import sys
from contextvars import ContextVar
from fastapi import Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
import json

# 定义全局的 Request ID ContextVar
request_id_context: ContextVar[str] = ContextVar("request_id", default="")

def setup_logger():
    """初始化和配置 Loguru 日志"""
    # 移除默认的处理器
    logger.remove()
    
    # 定义日志格式，注入 request_id
    def _log_format(record):
        req_id = request_id_context.get()
        if req_id:
            record["extra"]["request_id"] = req_id
            return "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <magenta>[{extra[request_id]}]</magenta> - <level>{message}</level>\\n"
        else:
            return "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | - <level>{message}</level>\\n"

    # 添加标准输出处理器
    logger.add(sys.stdout, format=_log_format, level="INFO")
    
    # 也可以选择添加 JSON 格式的文件输出（注释掉，目前仅输出到控制台）
    # logger.add("logs/app.log", format="{message}", level="INFO", serialize=True)

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 尝试从请求头中获取 X-Request-ID，否则生成新的
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # 将其存入 contextvar
        token = request_id_context.set(req_id)
        
        try:
            logger.info(f"Incoming request: {request.method} {request.url.path}")
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            # 清理上下文
            request_id_context.reset(token)
