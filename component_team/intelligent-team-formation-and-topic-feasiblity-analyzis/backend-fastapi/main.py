from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import database_status, init_database
from app.routes.cohort_routes import router as cohort_router
from app.routes.final_allocation_routes import router as final_allocation_router
from app.routes.supervisor_allocation_routes import router as supervisor_allocation_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield

app = FastAPI(
    title="Intelligent Team Formation and Topic Feasibility API",
    description="Staff-oriented decision-support API for undergraduate project team formation, topic technical feasibility, downstream supervisor allocation and persistence of confirmed final allocations.",
    version="3.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://127.0.0.1:3001", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cohort_router)
app.include_router(supervisor_allocation_router)
app.include_router(final_allocation_router)

@app.get("/")
def root():
    return {
        "message": "Intelligent Team Formation and Topic Feasibility API",
        "version": "V3.1",
        "status": "running",
        "active_workflows": [
            "Cohort workbook validation",
            "Heuristic-Seeded NSGA-II team formation",
            "Topic technical feasibility analysis",
            "Downstream supervisor allocation",
            "Final allocation persistence and PDF/Excel export",
        ],
        "database": database_status(),
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "database": database_status()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8003, reload=True)
