from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    query: str
    dataset: Optional[str] = "ecommerce_sales_2024.csv"
    session_id: Optional[str] = None


class TraceStepResponse(BaseModel):
    step_number: int
    thought: str
    action_type: str
    action_detail: Optional[str] = None
    observation_stdout: Optional[str] = None
    observation_error: Optional[str] = None
    plot_path: Optional[str] = None
    execution_time_ms: float = 0.0


class AnalyzeResponse(BaseModel):
    session_id: str
    status: str
    query: str
    final_answer: str
    plot_url: Optional[str] = None
    plot_filename: Optional[str] = None
    trace: List[TraceStepResponse]
    quality_evaluation: Optional[dict] = None
    execution_time_seconds: float


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    metadata: Optional[str] = None


class ArtifactResponse(BaseModel):
    id: int
    filename: str
    plot_url: str
    artifact_type: str
    created_at: datetime


class SessionDetailResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = []
    artifacts: List[ArtifactResponse] = []
    traces: List[TraceStepResponse] = []


class SessionSummaryResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    artifact_count: int = 0


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "chiron-agent-service"
    version: str = "0.2.0"
    llm_model: str
