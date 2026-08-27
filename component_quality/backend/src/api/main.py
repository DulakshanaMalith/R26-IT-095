from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.database import initialize_configured_database
from src.api.routers import analysis, review, resources, knowledge_graph, history, analytics, supervisor, auth
from src.api.services.core_logic import lifespan as model_lifespan, logger, REPORTS_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load existing ML models, then deliberately initialize configured data DB."""
    async with model_lifespan(app):
        database_url = initialize_configured_database()
        app.state.database_url = database_url
        if database_url:
            logger.info("PostgreSQL persistence configured; ensure Alembic migrations are applied.")
        else:
            logger.info("DATABASE_URL is not set; database-backed APIs will return 503.")
        yield

app = FastAPI(
    title="ResearchPilot API",
    description="Backend services for Exposía autonomous academic proposal review",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    """Return a lightweight backend health message."""
    return {"message": "Exposía AI Backend is running"}

app.mount("/reports", StaticFiles(directory=REPORTS_DIR), name="reports")

def include_routes(router: APIRouter) -> None:
    """Register APIRouter routes concretely for the active FastAPI runtime."""
    for route in router.routes:
        app.router.routes.append(route)


for api_router in (
    analysis.router,
    review.router,
    resources.router,
    knowledge_graph.router,
    history.router,
    analytics.router,
    supervisor.router,
    auth.router,
):
    include_routes(api_router)
