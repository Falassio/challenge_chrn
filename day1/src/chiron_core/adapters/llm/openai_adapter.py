from typing import List, Dict
import openai
from chiron_core.ports.llm_port import LLMPort


class OpenAILLMAdapter(LLMPort):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout: float = 60.0,
    ):
        if not api_key:
            raise ValueError("API key is required for OpenAILLMAdapter")

        self.model = model
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
    ) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
            )
            content = response.choices[0].message.content
            return content or ""
        except openai.AuthenticationError as e:
            raise RuntimeError(f"OpenAI Auth error: {e}") from e
        except openai.RateLimitError as e:
            raise RuntimeError(f"OpenAI Rate limit: {e}") from e
        except Exception as e:
            raise RuntimeError(f"LLM request failed: {type(e).__name__}: {str(e)}") from e
