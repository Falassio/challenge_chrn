from pathlib import Path
from typing import Optional, Union, Tuple, Any

from chiron_core.domain.models import AnalysisResult
from chiron_core.ports.llm_port import LLMPort
from chiron_core.ports.sandbox_port import SandboxPort
from chiron_core.ports.storage_port import SessionStoragePort
from chiron_core.engine.react_agent import ReActDataAgent


class AnalyzeDatasetUseCase:
    # caso d'uso che coordina l'agente e il salvataggio opzionale nel db
    def __init__(
        self,
        llm: LLMPort,
        sandbox: SandboxPort,
        storage: Optional[SessionStoragePort] = None,
        max_iterations: int = 5,
    ):
        self.llm = llm
        self.sandbox = sandbox
        self.storage = storage
        self.agent = ReActDataAgent(
            llm=llm,
            sandbox=sandbox,
            max_iterations=max_iterations,
        )

    def execute(
        self,
        query: str,
        dataset_path: Union[str, Path],
        session_id: Optional[str] = None,
    ) -> Tuple[AnalysisResult, Optional[Any]]:
        result = self.agent.run_analysis(query=query, dataset_path=dataset_path)

        session_record = None
        if self.storage:
            session_record = self.storage.save_analysis_turn(
                session_id=session_id or "",
                query=query,
                result=result,
            )

        return result, session_record
