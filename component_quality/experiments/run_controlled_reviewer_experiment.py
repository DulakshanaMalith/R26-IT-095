import os
import sys
import json
import logging
import argparse
import time
from pathlib import Path
from typing import List, Optional, Literal, Dict, Any

from pydantic import BaseModel, Field

# Add backend to path for ML imports
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from src.reviewer.providers import get_llm_provider
from src.reviewer.retrieval import get_retriever, format_rag_examples_for_prompt
from src.reviewer.criteria import load_criteria_as_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# Output Schemas
# ---------------------------------------------------------

class Issue(BaseModel):
    issue_id: str = Field(...)
    type: Literal["Weakness", "Strength"] = Field(...)
    severity: Literal["low", "medium", "high"] = Field(...)
    section: str = Field(...)
    evidence_span: str = Field(...)
    reason: str = Field(...)
    recommendation: str = Field(...)

class ReviewData(BaseModel):
    summary: str = Field(...)
    strengths: List[Issue] = Field(...)
    weaknesses: List[Issue] = Field(...)
    recommendations: List[str] = Field(...)
    overall_assessment: str = Field(...)

class MLData(BaseModel):
    weakness_predictions: List[str] = Field(default_factory=list)
    predicted_score: Optional[float] = Field(default=None)

class RAGData(BaseModel):
    retrieved_items: List[dict] = Field(default_factory=list)

class MetadataData(BaseModel):
    model: str = Field(...)
    temperature: float = Field(...)
    top_k: int = Field(...)
    timestamp: str = Field(...)
    experiment_id: str = Field(...)

class ExperimentReviewResult(BaseModel):
    evaluation_id: str = Field(...)
    system: str = Field(...)
    review: ReviewData = Field(...)
    ml: Optional[MLData] = Field(default=None)
    rag: Optional[RAGData] = Field(default=None)
    metadata: MetadataData = Field(...)

# ---------------------------------------------------------
# Experiment Runner
# ---------------------------------------------------------

class ExperimentRunner:
    def __init__(self, config_path: Path, experiment_id: str, is_dry_run: bool = False):
        self.config_path = config_path
        self.experiment_id = experiment_id
        self.is_dry_run = is_dry_run
        
        with config_path.open("r", encoding="utf-8") as f:
            self.config = json.load(f)
            
        self.base_dir = config_path.resolve().parent.parent
        self.results_dir = self.base_dir / "results" / self.experiment_id
        
        # Load dataset
        dataset_path = self.base_dir.parent / self.config["dataset"]["path"]
        self.dataset = []
        with dataset_path.open("r", encoding="utf-8") as f:
            for line in f:
                self.dataset.append(json.loads(line))
                
        # Prompts
        sys_path = self.base_dir.parent / self.config["prompts"]["system_prompt"]
        usr_path = self.base_dir.parent / self.config["prompts"]["user_prompt"]
        self.system_prompt = sys_path.read_text(encoding="utf-8")
        self.user_prompt_template = usr_path.read_text(encoding="utf-8")
        
        self.criteria_block = load_criteria_as_text()
        
        self.llm_provider = get_llm_provider()
        
        self.ml_weakness = None
        self.ml_grading = None
        self.retriever = None

    def load_artifacts(self, system: str):
        if "ml" in system:
            logger.info("Loading ML Models...")
            import joblib
            weakness_path = self.base_dir.parent / self.config["ml"]["weakness_model"]
            self.ml_weakness = joblib.load(weakness_path)
            grading_path = self.base_dir.parent / self.config["ml"]["grading_model"]
            self.ml_grading = joblib.load(grading_path)
            
        if "rag" in system:
            logger.info("Loading RAG Retriever...")
            self.retriever = get_retriever()
            # Force load index
            self.retriever._load_or_build_index()

    def run_system(self, system: str, limit: int = None, resume: bool = False):
        logger.info(f"--- Running System: {system} ---")
        
        self.load_artifacts(system)
        
        raw_dir = self.results_dir / "raw" / system
        norm_dir = self.results_dir / "normalized"
        raw_dir.mkdir(parents=True, exist_ok=True)
        norm_dir.mkdir(parents=True, exist_ok=True)
        
        proposals = self.dataset[:limit] if limit else self.dataset
        
        success_count = 0
        error_count = 0
        
        for p in proposals:
            eval_id = p["evaluation_id"]
            author_id = p["author_id"]
            text = p["proposal_text"]
            
            norm_file = norm_dir / f"{eval_id}_{system}.json"
            if resume and norm_file.exists():
                logger.info(f"[{eval_id}] Resuming (already exists)")
                success_count += 1
                continue
                
            logger.info(f"[{eval_id}] Evaluating...")
            
            if self.is_dry_run:
                continue
                
            try:
                # 1. RAG Component
                rag_examples = []
                historical_block = ""
                if "rag" in system:
                    # CRITICAL: Exclude the target author from RAG to prevent leakage
                    rag_examples = self.retriever.retrieve_similar_feedback(
                        query_text=text,
                        excluded_author_ids=[author_id],
                        top_k=self.config["rag"]["top_k"]
                    )
                    historical_block = format_rag_examples_for_prompt(rag_examples)
                
                # 2. ML Component
                ml_weakness_preds = []
                ml_score_pred = None
                context_block = ""
                if "ml" in system:
                    # Predict Score
                    ml_score_pred = float(self.ml_grading.predict([text])[0])
                    
                    # Predict Weaknesses
                    # Split into paragraphs like the training pipeline
                    import re
                    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
                    if paragraphs:
                        preds = self.ml_weakness.predict(paragraphs)
                        for para, pred in zip(paragraphs, preds):
                            if pred == 1:
                                ml_weakness_preds.append(para)
                                
                    if ml_score_pred or ml_weakness_preds:
                        context_block = "### AUTOMATED ML SIGNALS\n"
                        if ml_score_pred:
                            context_block += f"- Predicted Quality Score (0-42): {ml_score_pred:.1f}\n"
                        if ml_weakness_preds:
                            context_block += "- Detected potential weakness regions:\n"
                            for wp in ml_weakness_preds:
                                context_block += f"  > \"{wp[:100]}...\"\n"
                        context_block += "\nUse these ML signals as hints. Verify them before including in the review.\n\n"
                
                # 3. LLM Request
                user_prompt = self.user_prompt_template.format(
                    context_block=context_block,
                    historical_examples=historical_block,
                    criteria_block=self.criteria_block,
                    proposal_text=text
                )
                
                # Call LLM
                result, metadata = self.llm_provider.generate_structured(
                    system_prompt=self.system_prompt,
                    user_prompt=user_prompt,
                    response_model=ReviewData
                )
                
                # 4. Construct Final Normalized Output
                final_output = ExperimentReviewResult(
                    evaluation_id=eval_id,
                    system=system,
                    review=result,
                    ml=MLData(
                        weakness_predictions=ml_weakness_preds,
                        predicted_score=ml_score_pred
                    ) if "ml" in system else None,
                    rag=RAGData(
                        retrieved_items=rag_examples
                    ) if "rag" in system else None,
                    metadata=MetadataData(
                        model=metadata.get("model", "unknown"),
                        temperature=self.config["llm"]["temperature"],
                        top_k=self.config["rag"]["top_k"],
                        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        experiment_id=self.experiment_id
                    )
                )
                
                # Save normalized
                with norm_file.open("w", encoding="utf-8") as f:
                    f.write(final_output.model_dump_json(indent=2))
                    
                # Save raw (just the JSON string from LLM to verify exact LLM output)
                raw_file = raw_dir / f"{eval_id}_raw.json"
                with raw_file.open("w", encoding="utf-8") as f:
                    f.write(result.model_dump_json(indent=2))
                    
                success_count += 1
                
            except Exception as e:
                logger.error(f"[{eval_id}] Error: {e}", exc_info=True)
                error_count += 1
                error_file = norm_dir / f"{eval_id}_{system}_error.json"
                with error_file.open("w", encoding="utf-8") as f:
                    json.dump({
                        "evaluation_id": eval_id,
                        "system": system,
                        "status": "error",
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    }, f, indent=2)
                    
        return success_count, error_count

    def generate_manifest(self, systems: list):
        manifest_path = self.results_dir / "manifest.json"
        
        manifest = {
            "experiment_id": self.experiment_id,
            "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "dataset_version": "1.0",
            "number_of_proposals": len(self.dataset),
            "systems": systems,
            "llm_model": self.config["llm"]["model"],
            "temperature": self.config["llm"]["temperature"],
            "max_tokens": self.config["llm"]["max_tokens"],
            "prompt_versions": "v1",
            "rag_configuration": self.config["rag"],
            "ml_model_versions": self.config["ml"],
            "random_seeds": self.config["seeds"]
        }
        
        with manifest_path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

def main():
    parser = argparse.ArgumentParser(description="Run Controlled Reviewer Experiment")
    parser.add_argument("--experiment-id", required=True, help="Unique ID for this experiment run")
    parser.add_argument("--system", required=True, choices=["llm_only", "rag", "ml", "ml_rag", "all"], help="Which system to run")
    parser.add_argument("--config", default="experiments/configs/reviewer_experiment_v1.json", help="Path to config file")
    parser.add_argument("--limit", type=int, help="Limit number of proposals to process")
    parser.add_argument("--resume", action="store_true", help="Resume skipping already processed proposals")
    parser.add_argument("--dry-run", action="store_true", help="Validate everything but do not call LLM")
    
    args = parser.parse_args()
    
    config_path = Path(args.config)
    runner = ExperimentRunner(config_path, args.experiment_id, is_dry_run=args.dry_run)
    
    systems_to_run = ["llm_only", "rag", "ml", "ml_rag"] if args.system == "all" else [args.system]
    
    for sys_name in systems_to_run:
        succ, err = runner.run_system(sys_name, limit=args.limit, resume=args.resume)
        if not args.dry_run:
            logger.info(f"System {sys_name} complete. Success: {succ}, Error: {err}")
            
    if not args.dry_run:
        runner.generate_manifest(systems_to_run)
        logger.info("Experiment manifest generated.")

if __name__ == "__main__":
    main()
