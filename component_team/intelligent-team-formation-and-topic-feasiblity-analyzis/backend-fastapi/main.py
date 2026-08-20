from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.cohort_routes import (
    router as cohort_router,
)
from app.routes.supervisor_allocation_routes import (
    router as supervisor_allocation_router,
)


app = FastAPI(
    title=(
        "Intelligent Team Formation "
        "and Topic Feasibility API"
    ),
    description=(
        "Staff-oriented decision-support "
        "API for undergraduate project "
        "team formation, topic technical "
        "feasibility analysis, and "
        "downstream supervisor allocation."
    ),
    version="3.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(
    cohort_router
)

app.include_router(
    supervisor_allocation_router
)


@app.get("/")
def root():
    return {
        "message": (
            "Intelligent Team Formation "
            "and Topic Feasibility API"
        ),
        "version": "V3",
        "status": "running",
        "active_workflows": [
            (
                "Cohort workbook "
                "validation"
            ),
            (
                "Heuristic-Seeded "
                "NSGA-II team formation"
            ),
            (
                "Topic technical "
                "feasibility analysis"
            ),
            (
                "Downstream supervisor "
                "allocation"
            ),
        ],
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8003,
        reload=True,
    )