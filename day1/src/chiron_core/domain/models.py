from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    EXECUTE_CODE = "execute_code"
    FINAL_ANSWER = "final_answer"


class AgentAction(BaseModel):
    action_type: ActionType
    code: Optional[str] = None
    answer: Optional[str] = None


class Observation(BaseModel):
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    error: Optional[str] = None
    plot_path: Optional[str] = None
    execution_time_ms: float = 0.0

    @property
    def is_success(self) -> bool:
        return self.exit_code == 0 and not self.error


class Step(BaseModel):
    step_number: int
    thought: str
    action: AgentAction
    observation: Optional[Observation] = None
    # timestamp iso per ordinamento e storico nel db
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class ReasoningTrace(BaseModel):
    steps: List[Step] = Field(default_factory=list)

    def add_step(self, step: Step) -> None:
        self.steps.append(step)

    def format_for_prompt(self) -> str:
        # formatto lo storico dei passaggi così l'llm vede stdout e traceback
        if not self.steps:
            return ""
        
        formatted = []
        for s in self.steps:
            formatted.append(f"Step {s.step_number}:")
            formatted.append(f"Thought: {s.thought}")
            if s.action.action_type == ActionType.EXECUTE_CODE:
                formatted.append(f"Action: execute_code\n```python\n{s.action.code}\n```")
            else:
                formatted.append(f"Action: final_answer: {s.action.answer}")
            
            if s.observation:
                if s.observation.is_success:
                    obs_summary = s.observation.stdout.strip()
                    if s.observation.plot_path:
                        obs_summary += f"\n[Plotly HTML generated at: {s.observation.plot_path}]"
                    formatted.append(f"Observation: {obs_summary if obs_summary else 'Code executed successfully with no output.'}")
                else:
                    # passo l'errore/stderr così al giro dopo si corregge
                    err_msg = s.observation.error or s.observation.stderr.strip()
                    formatted.append(f"Observation (ERROR): {err_msg}")
        
        return "\n\n".join(formatted)


class AnalysisResult(BaseModel):
    status: str  # 'success' o 'error'
    query: str
    dataset_path: str
    final_answer: str
    plot_path: Optional[str] = None
    trace: ReasoningTrace
    total_steps: int = 0
    execution_time_seconds: float = 0.0
