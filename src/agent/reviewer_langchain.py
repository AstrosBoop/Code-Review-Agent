"""
代码审查 Agent - LangChain 版本
使用 LangChain 封装工具注册、Agent 执行、消息管理
"""
import os
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.tools import StructuredTool
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import SystemMessage

load_dotenv()

SYSTEM_PROMPT = (
    "你是一个专业的代码审查 Agent。对于用户提交的代码，你需要："
    "1. 调用 analyze_code_quality 分析代码质量"
    "2. 调用 check_security 检测安全漏洞"
    "3. 调用 suggest_optimizations 给出优化建议"
    "4. 根据发现的问题，调用 retrieve_knowledge 检索相关的最佳实践"
    "5. 最后综合所有工具的结果，生成一份结构清晰的中文代码审查报告\n"
    "报告格式：总体评分、质量问题、安全漏洞、优化建议、最佳实践参考、改进总结"
)


class CodeReviewAgentLC:
    """LangChain 版代码审查 Agent"""

    def __init__(self, knowledge_base, provider: str = "deepseek"):
        self.kb = knowledge_base
        self.llm = self._init_llm(provider)
        self.tools = self._build_tools()
        self.agent_executor = self._build_agent()

    def _init_llm(self, provider: str) -> ChatOpenAI:
        configs = {
            "deepseek": {
                "base_url": "https://api.deepseek.com",
                "key_env": "DEEPSEEK_API_KEY",
                "model": "deepseek-chat"
            },
            "openai": {
                "base_url": None,
                "key_env": "OPENAI_API_KEY",
                "model": "gpt-4o-mini"
            }
        }
        cfg = configs[provider]
        kwargs = {
            "model": cfg["model"],
            "api_key": os.getenv(cfg["key_env"]),
            "max_tokens": 2048,
        }
        if cfg["base_url"]:
            kwargs["base_url"] = cfg["base_url"]
        return ChatOpenAI(**kwargs)

    def _build_tools(self) -> list:
        from tools.code_analyzer import analyze_code_quality
        from tools.security_checker import check_security
        from tools.optimizer import suggest_optimizations

        def retrieve_knowledge(query: str) -> dict:
            results = self.kb.retrieve(query, top_k=3)
            return {
                "results": [
                    {
                        "title": r["document"]["info"]["title"],
                        "content": r["document"]["info"]["content"],
                        "category": r["document"]["info"]["category"]
                    }
                    for r in results
                ]
            }

        return [
            StructuredTool.from_function(
                func=analyze_code_quality,
                name="analyze_code_quality",
                description="分析代码质量，检测函数长度、命名规范、注释覆盖率、魔法数字等问题"
            ),
            StructuredTool.from_function(
                func=check_security,
                name="check_security",
                description="检测代码中的安全漏洞，包括 SQL 注入、硬编码密钥、命令注入、XSS 等"
            ),
            StructuredTool.from_function(
                func=suggest_optimizations,
                name="suggest_optimizations",
                description="分析代码性能和可维护性，给出优化建议"
            ),
            StructuredTool.from_function(
                func=retrieve_knowledge,
                name="retrieve_knowledge",
                description="从代码规范知识库中检索相关的最佳实践和规范说明"
            ),
        ]

    def _build_agent(self) -> AgentExecutor:
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=SYSTEM_PROMPT),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        agent = create_openai_tools_agent(self.llm, self.tools, prompt)
        return AgentExecutor(agent=agent, tools=self.tools, verbose=True, max_iterations=10)

    def review(self, code: str) -> dict:
        print("Step 1: LangChain Agent 开始分析代码...")
        result = self.agent_executor.invoke({
            "input": f"请审查以下代码：\n\n```\n{code}\n```"
        })
        print("Step 2: LangChain Agent 生成最终报告...")
        return {
            "report": result["output"],
            "tool_calls": len(self.agent_executor.middle) if hasattr(self.agent_executor, "middle") else "N/A"
        }
