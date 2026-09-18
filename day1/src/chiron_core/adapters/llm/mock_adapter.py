from typing import List, Dict, Optional
from chiron_core.ports.llm_port import LLMPort


class MockLLMAdapter(LLMPort):
    """Simple mock adapter for deterministic unit tests."""

    def __init__(self, responses: Optional[List[str]] = None):
        self.responses = list(responses) if responses else []
        self.call_count = 0
        self.history: List[List[Dict[str, str]]] = []

    def set_responses(self, responses: List[str]) -> None:
        self.responses = list(responses)
        self.call_count = 0

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
    ) -> str:
        self.history.append(messages)
        if not self.responses:
            return "Thought: No mock responses configured.\nAction: final_answer: Done."

        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return resp
        return self.responses[-1]
