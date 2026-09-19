from pathlib import Path
import os
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from chiron_service.config import get_service_settings, ServiceSettings
from chiron_service.storage.database import get_db
from chiron_service.storage.repository import SessionRepository
from chiron_service.api.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    SessionDetailResponse,
    SessionSummaryResponse,
    TraceStepResponse,
    MessageResponse,
    ArtifactResponse,
    HealthResponse,
)

from chiron_core.ports.llm_port import LLMPort
from chiron_core.adapters.llm import OpenAILLMAdapter, MockLLMAdapter
from chiron_core.adapters.sandbox import ProcessSandboxAdapter
from chiron_core.use_cases.analyze_dataset import AnalyzeDatasetUseCase
from chiron_core.engine.quality_evaluator import PlotQualityEvaluator
from chiron_core.config import get_settings as get_core_settings


router = APIRouter()


def resolve_dataset_path(dataset_ref: str, settings: ServiceSettings) -> Path:
    """
    Resolve dataset reference:
    1. Direct absolute/relative file path
    2. Lookup in data directory (e.g. day1/data/ecommerce_sales_2024.csv)
    """
    # controllo percorso diretto
    direct_path = Path(dataset_ref)
    if direct_path.exists() and direct_path.is_file():
        return direct_path

    # controllo nella cartella data
    data_dir = Path(settings.data_dir)
    in_data_dir = data_dir / dataset_ref
    if in_data_dir.exists() and in_data_dir.is_file():
        return in_data_dir

    # controllo percorso relativo day1/data
    alt_data_dir = Path("day1/data") / dataset_ref
    if alt_data_dir.exists() and alt_data_dir.is_file():
        return alt_data_dir

    # elenco file per il messaggio di errore 404
    available = []
    if data_dir.exists():
        available = [f.name for f in data_dir.glob("*.csv")]

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Dataset '{dataset_ref}' not found. Available datasets: {available}",
    )


def get_llm_adapter() -> LLMPort:
    
    core_settings = get_core_settings()
    api_key = core_settings.openai_api_key or os.getenv("OPENAI_API_KEY", "")
    
    if not api_key:
        # se non c'è api key uso il mock deterministico
        return MockLLMAdapter(responses=[
            "Thought: Executing mock analysis.\nAction: execute_code\n```python\nimport pandas as pd\ndf = pd.read_csv('data.csv')\nprint('Total:', len(df))\n```",
            "Thought: Analysis complete.\nAction: final_answer: Analysis completed successfully using mock provider."
        ])

    return OpenAILLMAdapter(
        api_key=api_key,
        base_url=core_settings.openai_base_url,
        model=core_settings.openai_model,
    )


@router.post("/analyze", response_model=AnalyzeResponse, summary="Analyze dataset and generate visualization")
def analyze_dataset(
    request: AnalyzeRequest,
    db: Session = Depends(get_db),
    llm: LLMPort = Depends(get_llm_adapter),
    settings: ServiceSettings = Depends(get_service_settings),
):
    
    if not request.query.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The 'query' field cannot be empty.",
        )

    # risolvo il percorso del dataset
    dataset_path = resolve_dataset_path(request.dataset or "ecommerce_sales_2024.csv", settings)

    # preparo sandbox e caso d'uso
    core_settings = get_core_settings()
    sandbox = ProcessSandboxAdapter(
        timeout_seconds=core_settings.sandbox_timeout_seconds,
        output_dir=settings.output_dir,
    )
    repo = SessionRepository(db)
    use_case = AnalyzeDatasetUseCase(
        llm=llm,
        sandbox=sandbox,
        storage=repo,
        max_iterations=core_settings.max_iterations,
    )

    # eseguo l'analisi
    result, session = use_case.execute(
        query=request.query,
        dataset_path=dataset_path,
        session_id=request.session_id,
    )

    # preparo la risposta
    plot_url = None
    plot_filename = None
    quality_eval = None
    if result.plot_path and Path(result.plot_path).exists():
        p_path = Path(result.plot_path)
        plot_filename = p_path.name
        plot_url = f"/plots/{p_path.name}"
        quality_eval = PlotQualityEvaluator.evaluate(result.plot_path)

    trace_responses = []
    for s in result.trace.steps:
        action_detail = s.action.code or s.action.answer
        obs_stdout = s.observation.stdout if s.observation else None
        obs_err = s.observation.error if s.observation else None
        obs_time = s.observation.execution_time_ms if s.observation else 0.0
        obs_plot = s.observation.plot_path if s.observation else None

        trace_responses.append(
            TraceStepResponse(
                step_number=s.step_number,
                thought=s.thought,
                action_type=s.action.action_type.value,
                action_detail=action_detail,
                observation_stdout=obs_stdout,
                observation_error=obs_err,
                plot_path=obs_plot,
                execution_time_ms=obs_time,
            )
        )

    return AnalyzeResponse(
        session_id=session.id,
        status=result.status,
        query=request.query,
        final_answer=result.final_answer,
        plot_url=plot_url,
        plot_filename=plot_filename,
        trace=trace_responses,
        quality_evaluation=quality_eval,
        execution_time_seconds=result.execution_time_seconds,
    )


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse, summary="Retrieve session history")
def get_session_history(
    session_id: str,
    db: Session = Depends(get_db),
):
    
    repo = SessionRepository(db)
    session = repo.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID '{session_id}' was not found.",
        )

    messages = [
        MessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
            metadata=m.metadata_json,
        )
        for m in session.messages
    ]

    artifacts = [
        ArtifactResponse(
            id=a.id,
            filename=a.filename,
            plot_url=f"/plots/{a.filename}",
            artifact_type=a.artifact_type,
            created_at=a.created_at,
        )
        for a in session.artifacts
    ]

    traces = [
        TraceStepResponse(
            step_number=t.step_number,
            thought=t.thought,
            action_type=t.action_type,
            action_detail=t.action_detail,
            observation_stdout=t.observation_stdout,
            observation_error=t.observation_error,
            plot_path=t.plot_path,
            execution_time_ms=t.execution_time_ms,
        )
        for t in session.traces
    ]

    return SessionDetailResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=messages,
        artifacts=artifacts,
        traces=traces,
    )


@router.get("/sessions", response_model=List[SessionSummaryResponse], summary="List past sessions")
def list_sessions(
    limit: int = 20,
    db: Session = Depends(get_db),
):
    
    repo = SessionRepository(db)
    sessions = repo.list_sessions(limit=limit)
    return [
        SessionSummaryResponse(
            id=s.id,
            title=s.title,
            created_at=s.created_at,
            updated_at=s.updated_at,
            message_count=len(s.messages),
            artifact_count=len(s.artifacts),
        )
        for s in sessions
    ]


@router.get("/plots/{filename}", summary="Serve generated Plotly HTML visualization")
def serve_plot(
    filename: str,
    settings: ServiceSettings = Depends(get_service_settings),
):
    
    # controllo di sicurezza contro path traversal
    safe_filename = Path(filename).name
    if not safe_filename.endswith(".html"):
        raise HTTPException(status_code=400, detail="Only .html plot files are served.")

    target_path = Path(settings.output_dir) / safe_filename
    if not target_path.exists():
        # controllo se è il file di esempio in day1
        example_fallback = Path("day1/examples") / safe_filename
        if example_fallback.exists():
            target_path = example_fallback
        else:
            raise HTTPException(status_code=404, detail="Plot file not found.")

    return FileResponse(
        path=target_path,
        media_type="text/html",
        filename=safe_filename,
    )


@router.get("/health", response_model=HealthResponse, summary="Healthcheck endpoint")
def healthcheck():
    
    core_settings = get_core_settings()
    return HealthResponse(
        status="ok",
        service="chiron-agent-service",
        version="0.2.0",
        llm_model=core_settings.openai_model,
    )


@router.get("/datasets", summary="List available datasets")
def list_available_datasets(settings: ServiceSettings = Depends(get_service_settings)):
    
    data_dir = Path(settings.data_dir)
    datasets = []
    if data_dir.exists():
        for f in data_dir.glob("*.csv"):
            datasets.append({
                "filename": f.name,
                "size_kb": round(f.stat().st_size / 1024, 2),
                "path": str(f),
            })
    return {"datasets": datasets}
