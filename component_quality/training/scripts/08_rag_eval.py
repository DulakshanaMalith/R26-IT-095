import sys
import logging
import json
import random
from pathlib import Path
import numpy as np

import joblib
from sentence_transformers import SentenceTransformer, util

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

def main():
    script_dir = Path(__file__).resolve().parent
    models_dir = (script_dir / "../models").resolve()
    exp_dir = (script_dir / "../models/experiments").resolve()
    
    rag_path = models_dir / "feedback_embeddings.pkl"
    if not rag_path.exists():
        logger.error(f"Cannot find RAG artifact at {rag_path}")
        return
        
    logger.info("Loading RAG artifact...")
    artifact = joblib.load(rag_path)
    corpus_embeddings = artifact["embeddings"]
    corpus_texts = artifact["texts"]
    corpus_comments = artifact.get("comments", [])
    model_name = artifact.get("model_name", "all-MiniLM-L6-v2")
    
    logger.info(f"Loading SentenceTransformer: {model_name}...")
    model = SentenceTransformer(model_name)
    
    # Generate random queries by sampling from the corpus itself (simulating student proposals)
    random.seed(42)
    sample_indices = random.sample(range(len(corpus_texts)), 30)
    
    results = []
    
    for idx in sample_indices:
        query_text = corpus_texts[idx]
        query_embedding = model.encode(query_text, convert_to_tensor=True)
        
        # Compute similarities
        cos_scores = util.cos_sim(query_embedding, corpus_embeddings)[0]
        top_results = np.argsort(cos_scores.cpu().numpy())[::-1][:6] # Get top 6, drop 1st if it is exactly the query
        
        retrieved = []
        for i in top_results:
            if i == idx: continue # Ignore exact identity match since we sampled from corpus
            retrieved.append({
                "score": float(cos_scores[i]),
                "text": corpus_texts[i],
                "comment": corpus_comments[i] if corpus_comments else None
            })
            if len(retrieved) == 5:
                break
                
        results.append({
            "query": query_text,
            "top_5": retrieved
        })
        
    # Write report
    md_content = "# RAG Qualitative Evaluation\n\n"
    md_content += "This report samples 30 historical proposal chunks and queries the RAG system to retrieve the top-5 most similar historical feedbacks.\n"
    md_content += "> Note: Quantitative Recall@K cannot be computed as there is no isolated hold-out query set with known relevance judgments. Manual categorization is required.\n\n"
    
    for i, res in enumerate(results):
        md_content += f"## Query {i+1}\n"
        md_content += f"**Student Proposal Chunk:**\n> {res['query'][:500]}...\n\n"
        md_content += "**Retrieved Feedback:**\n"
        for j, ret in enumerate(res['top_5']):
            md_content += f"**{j+1}. [Sim: {ret['score']:.3f}]** {ret['comment']}\n"
        md_content += "\n---\n"
        
    with (exp_dir / "rag_qualitative_eval.json").open("w") as f:
        json.dump(results, f, indent=4)
        
    with (exp_dir / "rag_qualitative_eval.md").open("w") as f:
        f.write(md_content)
        
    logger.info("RAG Evaluation complete.")

if __name__ == "__main__":
    main()
