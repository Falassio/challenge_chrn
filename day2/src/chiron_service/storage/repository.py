from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from chiron_service.storage.models import SessionModel, MessageModel, TraceStepModel, ArtifactModel
from chiron_core.domain.models import AnalysisResult, ActionType
from chiron_core.ports.storage_port import SessionStoragePort


class SessionRepository(SessionStoragePort):
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_session(self, session_id: Optional[str] = None, title: Optional[str] = None) -> SessionModel:
        # se esiste già la riprendo, sennò ne creo una nuova
        if session_id:
            session = self.db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            ).scalar_one_or_none()
            if session:
                return session

        new_id = session_id or str(uuid.uuid4())
        new_title = title or "Data Analysis Session"
        new_session = SessionModel(
            id=new_id,
            title=new_title,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(new_session)
        self.db.commit()
        self.db.refresh(new_session)
        return new_session

    def get_session(self, session_id: str) -> Optional[SessionModel]:
        return self.db.execute(
            select(SessionModel).where(SessionModel.id == session_id)
        ).scalar_one_or_none()

    def list_sessions(self, limit: int = 50) -> List[SessionModel]:
        # ultime sessioni aggiornate
        return list(
            self.db.execute(
                select(SessionModel).order_by(desc(SessionModel.updated_at)).limit(limit)
            ).scalars().all()
        )

    def save_analysis_turn(
        self,
        session_id: Optional[str] = None,
        query: str = "",
        result: Optional[AnalysisResult] = None,
    ) -> SessionModel:
        # salvo la domanda dell'utente, la risposta dell'assistente, i passaggi e il grafico
        session = self.get_or_create_session(session_id=session_id)
        session.updated_at = datetime.now(timezone.utc)

        # 1. messaggio utente
        user_msg = MessageModel(
            session_id=session.id,
            role="user",
            content=query,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(user_msg)

        # 2. risposta assistente
        assistant_msg = MessageModel(
            session_id=session.id,
            role="assistant",
            content=result.final_answer,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(assistant_msg)

        # 3. passaggi del reasoning trace
        for s in result.trace.steps:
            action_detail = None
            if s.action.action_type == ActionType.EXECUTE_CODE:
                action_detail = s.action.code
            elif s.action.action_type == ActionType.FINAL_ANSWER:
                action_detail = s.action.answer

            obs_stdout = s.observation.stdout if s.observation else None
            obs_stderr = s.observation.stderr if s.observation else None
            obs_exit = s.observation.exit_code if s.observation else None
            obs_err = s.observation.error if s.observation else None
            obs_plot = s.observation.plot_path if s.observation else None
            obs_time = s.observation.execution_time_ms if s.observation else 0.0

            step_record = TraceStepModel(
                session_id=session.id,
                step_number=s.step_number,
                thought=s.thought,
                action_type=s.action.action_type.value,
                action_detail=action_detail,
                observation_stdout=obs_stdout,
                observation_stderr=obs_stderr,
                observation_exit_code=obs_exit,
                observation_error=obs_err,
                plot_path=obs_plot,
                execution_time_ms=obs_time,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(step_record)

        # 4. salvo l'artefatto se è stato prodotto un grafico
        if result.plot_path and Path(result.plot_path).exists():
            plot_file = Path(result.plot_path)
            artifact = ArtifactModel(
                session_id=session.id,
                filename=plot_file.name,
                file_path=str(plot_file.resolve()),
                artifact_type="plotly_html",
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(artifact)

        self.db.commit()
        self.db.refresh(session)
        return session
