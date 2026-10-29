"""Application entrypoint for the AI Exam Paper Evaluation System backend service."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import logger
from app.database.session import init_db
from app.api.v1 import api_v1_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown event handler."""
    logger.info("Initializing KTU AI Exam Evaluation System backend...")
    try:
        await init_db()
        logger.info("Database models initialized successfully.")
    except Exception as exc:
        logger.warning(f"Database initialization warning: {exc}")
    yield
    logger.info("Backend service shutting down cleanly.")


app = FastAPI(
    title="KTU AI Handwritten Answer Evaluation Platform",
    description="Production-quality AI evaluation platform for KTU Theory Examinations (Constitution of India, Industrial Economics, Professional Ethics).",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Versioned API Routers
app.include_router(api_v1_router, prefix="/api")


@app.get("/", tags=["Health"])
async def root():
    """Root health check endpoint."""
    return {
        "status": "ONLINE",
        "service": "KTU AI Handwritten Answer Evaluation Platform",
        "environment": settings.ENVIRONMENT,
        "ocr_engine": settings.OCR_ENGINE,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL,
        "vector_db": settings.VECTOR_DB,
    }


@app.get("/api", tags=["Health"])
async def api_root():
    return await root()


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check endpoint."""
    return {
        "status": "HEALTHY",
        "supported_subjects": settings.subject_list,
        "confidence_threshold": settings.CONFIDENCE_THRESHOLD,
    }


@app.get("/api/health", tags=["Health"])
async def api_health_check():
    return await health_check()
