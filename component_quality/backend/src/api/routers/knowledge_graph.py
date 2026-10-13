from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import Response
from src.api.schemas import *
from src.api.services.core_logic import *

router = APIRouter()

@router.post("/knowledge-graph", response_model=KnowledgeGraphResponse)
def create_knowledge_graph(payload: KnowledgeGraphRequest) -> KnowledgeGraphResponse:
    """Extract proposal concepts and return a lightweight concept graph."""
    print("[MODEL DEBUG] Endpoint /knowledge-graph called")
    cleaned_text = clean_text(payload.text)
    validate_research_proposal_text(cleaned_text, payload.analysis_id)
    text = prepare_model_text(cleaned_text)
    try:
        graph = analyze_knowledge_graph(text)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Knowledge graph analysis failed: {exc}",
        ) from exc

    save_graph_history(analysis_id=payload.analysis_id, filename=payload.filename, graph=graph)
    graph["analysis_id"] = payload.analysis_id
    print(
        "[MODEL DEBUG] Knowledge graph generated:",
        len(graph.get("concepts", [])),
        "concepts",
        len(graph.get("edges", [])),
        "edges",
    )
    return KnowledgeGraphResponse(**graph)

@router.get("/knowledge-graph-history", response_model=HistoryResponse)
def get_knowledge_graph_history() -> HistoryResponse:
    """Return saved knowledge graph summaries, newest first."""
    history = load_graph_history()
    newest_first = list(reversed(history))
    return HistoryResponse(total=len(history), items=newest_first[:50])