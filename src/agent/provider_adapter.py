import os
from openai import OpenAI
from loguru import logger
import time
from typing import Tuple, Dict, Any

class LLMProviderAdapter:
    def __init__(self, provider: str = "openai"):
        self.provider = provider
        # 这里预留了多种 Provider 的扩展可能
        # MVP 阶段主要打通 OpenAI / DeepSeek
        if self.provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY", "your-openai-key")
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            self.client = OpenAI(api_key=api_key, base_url=base_url)
            self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        elif self.provider == "deepseek":
            api_key = os.getenv("DEEPSEEK_API_KEY", "your-deepseek-key")
            base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
            self.client = OpenAI(api_key=api_key, base_url=base_url)
            self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def generate(self, system_prompt: str, user_prompt: str) -> Tuple[str, int, int]:
        """
        调用 LLM 生成内容，返回 (响应文本, 输入_tokens, 输出_tokens)
        为了面试展示，这里的 Token 消耗被专门剥离出来，用于 metrics 统计
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2
            )
            
            content = response.choices[0].message.content
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0
            
            return content, input_tokens, output_tokens
            
        except Exception as e:
            logger.exception(f"LLM API Error using {self.provider}")
            raise e

# 默认实例
default_llm = LLMProviderAdapter(provider=os.getenv("DEFAULT_LLM_PROVIDER", "openai"))
