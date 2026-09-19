from contextlib import asynccontextmanager
import time
import uuid
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from chiron_service.storage.database import init_db
from chiron_service.api.routes import router
from chiron_service.config import get_service_settings

logger = logging.getLogger("chiron.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    
    logger.info("Initializing database tables...")
    init_db()
    yield
    logger.info("Shutting down Chiron Agent Service.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Chiron Data Analysis Agent Service",
        description="Production-ready REST API for ReAct Data Analysis with Plotly Visualizations",
        version="0.2.0",
        lifespan=lifespan,
    )

    # cors abilitato per chiamate locali
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # middleware per loggare tempi e id richiesta
    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start_time = time.perf_counter()
        
        # id per tracciare la richiesta
        request.state.request_id = request_id

        response = await call_next(request)
        
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
        
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} -> {response.status_code} ({duration_ms:.1f}ms)"
        )
        return response

    # gestione errori 500 generici
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception on {request.url.path}: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred while processing the request.",
                "details": str(exc),
            }
        )

    # collego i router delle api
    app.include_router(router)

    return app
