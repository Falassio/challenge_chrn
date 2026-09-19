from abc import ABC, abstractmethod
from typing import Optional, List, Any
from chiron_core.domain.models import AnalysisResult


class SessionStoragePort(ABC):
    # interfaccia astratta per la persistenza su sqlite/postgres
    @abstractmethod
    def get_or_create_session(self, session_id: Optional[str] = None, title: Optional[str] = None) -> Any:
        pass

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[Any]:
        pass

    @abstractmethod
    def list_sessions(self, limit: int = 50) -> List[Any]:
        pass

    @abstractmethod
    def save_analysis_turn(
        self,
        session_id: Optional[str],
        query: str,
        result: AnalysisResult,
    ) -> Any:
        pass
