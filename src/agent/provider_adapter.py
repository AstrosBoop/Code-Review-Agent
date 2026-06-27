import os
from openai import OpenAI
from loguru import logger
import time
from typing import Tuple, Dict, Any

class LLMProviderAdapter:
    def __init__(self, provider_name: str = "openai", timeout_seconds: int = 30):
        self.provider_name = provider_name.lower()
        self.timeout_seconds = timeout_seconds
        
        # 初始化客户端（如果无 key 可以在运行时 catch）
        try:
            if self.provider_name == "openai":
                self.client = OpenAI(timeout=self.timeout_seconds)
                self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            elif self.provider_name == "deepseek":
                self.client = OpenAI(
                    api_key=os.environ.get("DEEPSEEK_API_KEY", "dummy_key"),
                    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                    timeout=self.timeout_seconds
                )
                self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
            else:
                raise ValueError(f"Unsupported provider: {provider_name}")
        except Exception as e:
            logger.warning(f"Failed to initialize {self.provider_name} client: {e}. Will use mock fallback.")
            self.client = None

    def generate(self, system_prompt: str, user_prompt: str) -> Tuple[str, int, int]:
        """
        统一的生成接口
        返回: (生成文本, input_tokens, output_tokens)
        """
        # 如果未初始化客户端或缺少关键配置，直接走兜底
        if not self.client:
            return self._mock_fallback()

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
            
        except OpenAIError as e:
            logger.error(f"LLM API Error with provider {self.provider_name}: {e}")
            logger.warning("Falling back to mock provider.")
            return self._mock_fallback()
        except Exception as e:
            logger.error(f"Unexpected error with provider {self.provider_name}: {e}")
            logger.warning("Falling back to mock provider.")
            return self._mock_fallback()
            
    def _mock_fallback(self) -> Tuple[str, int, int]:
        """兜底机制：返回 Mock 的分析报告"""
        mock_report = "### Mock 报告\n\n系统目前未配置有效的 API Key 或网络请求失败，已触发降级保护机制。代码静态分析仍可用，请配置有效的密钥后重试。"
        return mock_report, 10, 50

default_llm = LLMProviderAdapter(provider_name=os.getenv("DEFAULT_LLM_PROVIDER", "openai"))
