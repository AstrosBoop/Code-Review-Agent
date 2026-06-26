"""
代码审查 Agent 核心逻辑
使用 Function Calling 调度多个工具
"""
import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# 定义工具列表（Function Calling）
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "analyze_code_quality",
            "description": "分析代码质量，检测函数长度、命名规范、注释覆盖率、魔法数字等问题",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "需要分析的代码"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_security",
            "description": "检测代码中的安全漏洞，包括 SQL 注入、硬编码密钥、命令注入、XSS 等",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "需要检测的代码"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_optimizations",
            "description": "分析代码性能和可维护性，给出优化建议",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "需要优化的代码"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_knowledge",
            "description": "从代码规范知识库中检索相关的最佳实践和规范说明",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索关键词，如'SQL注入'、'命名规范'等"}
                },
                "required": ["query"]
            }
        }
    }
]


class CodeReviewAgent:
    """代码审查 Agent"""

    def __init__(self, knowledge_base, provider: str = "deepseek"):
        self.kb = knowledge_base
        self.client, self.model = self._init_client(provider)

        # 延迟导入工具函数
        from tools.code_analyzer import analyze_code_quality
        from tools.security_checker import check_security
        from tools.optimizer import suggest_optimizations

        self.tool_functions = {
            "analyze_code_quality": analyze_code_quality,
            "check_security": check_security,
            "suggest_optimizations": suggest_optimizations,
            "retrieve_knowledge": self._retrieve_knowledge
        }

    def _init_client(self, provider: str):
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
        kwargs = {"api_key": os.getenv(cfg["key_env"])}
        if cfg["base_url"]:
            kwargs["base_url"] = cfg["base_url"]
        return OpenAI(**kwargs), cfg["model"]

    def _retrieve_knowledge(self, query: str) -> dict:
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

    def _call_tool(self, tool_name: str, tool_args: dict) -> str:
        func = self.tool_functions.get(tool_name)
        if func is None:
            return json.dumps({"error": f"未知工具: {tool_name}"})
        result = func(**tool_args)
        return json.dumps(result, ensure_ascii=False)

    def review(self, code: str) -> dict:
        """
        对代码进行完整审查
        使用 Function Calling 让 LLM 自主决定调用哪些工具
        """
        print("Step 1: Agent 开始分析代码...")

        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个专业的代码审查 Agent。对于用户提交的代码，你需要："
                    "1. 调用 analyze_code_quality 分析代码质量"
                    "2. 调用 check_security 检测安全漏洞"
                    "3. 调用 suggest_optimizations 给出优化建议"
                    "4. 根据发现的问题，调用 retrieve_knowledge 检索相关的最佳实践"
                    "5. 最后综合所有工具的结果，生成一份结构清晰的中文代码审查报告"
                    "报告格式：总体评分、质量问题、安全漏洞、优化建议、最佳实践参考、改进总结"
                )
            },
            {
                "role": "user",
                "content": f"请审查以下代码：\n\n```\n{code}\n```"
            }
        ]

        # Function Calling 循环
        tool_call_count = 0
        while tool_call_count < 10:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=2048
            )

            message = response.choices[0].message

            # 没有工具调用，说明 Agent 已完成
            if not message.tool_calls:
                print("Step 2: Agent 生成最终报告...")
                return {
                    "report": message.content,
                    "tool_calls": tool_call_count
                }

            # 执行工具调用
            messages.append(message)
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                print(f"  → 调用工具: {tool_name}")

                result = self._call_tool(tool_name, tool_args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
                tool_call_count += 1

        return {"report": "审查超时，工具调用次数超限", "tool_calls": tool_call_count}
