from abc import ABC, abstractmethod
from typing import List, Dict


class LLMPort(ABC):
    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
    ) -> str:
        pass
