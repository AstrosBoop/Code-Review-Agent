import time
import json
from typing import TypedDict, Dict, Any, Annotated
from langgraph.graph import StateGraph, END
from loguru import logger
from src.agent.provider_adapter import default_llm

def merge_dicts(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    c = a.copy() if a else {}
    if b:
        c.update(b)
    return c

class ReviewState(TypedDict):
    code: str
    filename: str
    static_results: Dict[str, Any]
    rag_context: str
    security_report: str
    quality_report: str
    performance_report: str
    final_report: str
    metrics: Annotated[Dict[str, Any], merge_dicts]

def run_static_tools_node(state: ReviewState):
    """静态分析节点 (Placeholder)"""
    logger.info(f"Running static tools for {state.get('filename')}")
    start_time = time.time()
    
    # 这里将来集成 flake8, bandit 等工具
    # 目前作为桩代码返回一些假数据
    static_results = {"lint": "Pass", "cyclomatic_complexity": 5}
    
    metrics = state.get("metrics", {})
    metrics["static_analysis_time"] = time.time() - start_time
    
    return {"static_results": static_results, "metrics": metrics}

def retrieve_rag_node(state: ReviewState):
    """RAG 上下文检索节点 (Placeholder)"""
    logger.info(f"Retrieving RAG context for {state.get('filename')}")
    start_time = time.time()
    
    try:
        # 模拟检索操作（后续可以抛出异常测试降级）
        rag_context = "Best practices: Use contextvars for request tracking. Always close database connections."
    except Exception as e:
        logger.warning(f"RAG unavailable: {e}. Fallback to built-in coding guidelines.")
        rag_context = "使用内置代码规范：安全、可读性、性能、异常处理、输入校验..."
    
    metrics = state.get("metrics", {})
    metrics["rag_retrieval_time"] = time.time() - start_time
    
    return {"rag_context": rag_context, "metrics": metrics}

def security_reviewer_node(state: ReviewState):
    """安全性审查并发节点"""
    logger.info("Running Security Reviewer")
    start_time = time.time()
    
    sys_prompt = "You are a senior security reviewer. Analyze the code for vulnerabilities like SQL injection, XSS, etc. Use the provided static analysis and RAG context."
    user_prompt = f"Filename: {state['filename']}\\nCode:\\n{state['code']}\\n\\nRAG Context: {state['rag_context']}"
    
    report, in_tokens, out_tokens = default_llm.generate(sys_prompt, user_prompt)
    
    metrics = state.get("metrics", {})
    metrics["security_reviewer_time"] = time.time() - start_time
    metrics["security_tokens_in"] = in_tokens
    metrics["security_tokens_out"] = out_tokens
    
    return {"security_report": report, "metrics": metrics}

def quality_reviewer_node(state: ReviewState):
    """代码质量审查并发节点"""
    logger.info("Running Quality Reviewer")
    start_time = time.time()
    
    sys_prompt = "You are a code quality expert. Check for readability, maintainability, SOLID principles, and naming conventions."
    user_prompt = f"Filename: {state['filename']}\\nCode:\\n{state['code']}\\n\\nStatic Results: {json.dumps(state.get('static_results', {}))}"
    
    report, in_tokens, out_tokens = default_llm.generate(sys_prompt, user_prompt)
    
    metrics = state.get("metrics", {})
    metrics["quality_reviewer_time"] = time.time() - start_time
    metrics["quality_tokens_in"] = in_tokens
    metrics["quality_tokens_out"] = out_tokens
    
    return {"quality_report": report, "metrics": metrics}

def performance_reviewer_node(state: ReviewState):
    """性能审查并发节点"""
    logger.info("Running Performance Reviewer")
    start_time = time.time()
    
    sys_prompt = "You are a performance engineer. Analyze the code for efficiency, time complexity, resource leaks, and potential bottlenecks."
    user_prompt = f"Filename: {state['filename']}\\nCode:\\n{state['code']}"
    
    report, in_tokens, out_tokens = default_llm.generate(sys_prompt, user_prompt)
    
    metrics = state.get("metrics", {})
    metrics["performance_reviewer_time"] = time.time() - start_time
    metrics["performance_tokens_in"] = in_tokens
    metrics["performance_tokens_out"] = out_tokens
    
    return {"performance_report": report, "metrics": metrics}

def synthesizer_node(state: ReviewState):
    """结果聚合节点"""
    logger.info("Synthesizing final report")
    start_time = time.time()
    
    sys_prompt = "You are the lead architect. Synthesize the reports from the Security, Quality, and Performance teams into a single, cohesive, well-structured final markdown review."
    user_prompt = (
        f"Security Report:\\n{state.get('security_report', 'N/A')}\\n\\n"
        f"Quality Report:\\n{state.get('quality_report', 'N/A')}\\n\\n"
        f"Performance Report:\\n{state.get('performance_report', 'N/A')}"
    )
    
    report, in_tokens, out_tokens = default_llm.generate(sys_prompt, user_prompt)
    
    metrics = state.get("metrics", {})
    metrics["synthesizer_time"] = time.time() - start_time
    metrics["synthesizer_tokens_in"] = in_tokens
    metrics["synthesizer_tokens_out"] = out_tokens
    
    # 计算总时间
    if "workflow_start_time" in metrics:
        metrics["total_workflow_time"] = time.time() - metrics["workflow_start_time"]
        
    return {"final_report": report, "metrics": metrics}

def build_review_graph():
    """构建多节点审查图"""
    workflow = StateGraph(ReviewState)

    # 添加所有节点
    workflow.add_node("static_tools", run_static_tools_node)
    workflow.add_node("rag_retrieval", retrieve_rag_node)
    
    workflow.add_node("security_reviewer", security_reviewer_node)
    workflow.add_node("quality_reviewer", quality_reviewer_node)
    workflow.add_node("performance_reviewer", performance_reviewer_node)
    
    workflow.add_node("synthesizer", synthesizer_node)

    # 绘制边 (串行与并行控制)
    workflow.set_entry_point("static_tools")
    workflow.add_edge("static_tools", "rag_retrieval")
    
    # 并行分发: RAG 完成后，分发给三个并发 Reviewer
    workflow.add_edge("rag_retrieval", "security_reviewer")
    workflow.add_edge("rag_retrieval", "quality_reviewer")
    workflow.add_edge("rag_retrieval", "performance_reviewer")
    
    # 并行汇聚: 这三个节点都必须完成后才能进入 synthesizer
    # LangGraph 的 default behavior 对于多个 incoming edges 到一个 node 并不是等待全部。
    # 实际上 LangGraph state update 是增量的。要实现聚合，我们需要设置所有分支指向 synthesizer。
    # 在 LangGraph v0 中，多条边指向一个节点会自动作为合并节点 (会等待所有的 previous nodes 跑完)。
    workflow.add_edge("security_reviewer", "synthesizer")
    workflow.add_edge("quality_reviewer", "synthesizer")
    workflow.add_edge("performance_reviewer", "synthesizer")
    
    workflow.add_edge("synthesizer", END)
    
    return workflow.compile()
