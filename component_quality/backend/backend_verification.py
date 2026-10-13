import sys
import logging
from pathlib import Path
from fastapi.testclient import TestClient

# Add backend to path so we can import src
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

try:
    from src.api.main import app
except Exception as e:
    print(f"Failed to import backend app: {e}")
    sys.exit(1)

client = TestClient(app)

def test_endpoints():
    proposals = {
        "short_proposal": "This is a very short text that is definitely not a research proposal. But it has the word methodology and research gap.",
        "medium_proposal": "Abstract\nThis research investigates the usage of AI in healthcare. Research Gap\nCurrently, there is no AI that can do everything. Objectives\nRQ1: What is AI? RQ2: How to use it? Methodology\nWe will use a survey. Evaluation\nWe evaluate using MAE.",
        "long_proposal": "Abstract\nThis is a comprehensively written proposal about artificial intelligence and education. \n\nResearch Gap\nThere are numerous gaps in the existing literature regarding the deployment of generative models in high school math. \n\nObjectives\nOur main objective is to measure the efficacy of ITS. \n\nMethodology\nWe will conduct a randomized controlled trial with N=500 students. We will evaluate their test scores before and after using the AI tool. \n\nEvaluation\nWe evaluate using standardized metrics.",
        "weak_incomplete": "Abstract\nI want to do AI. Research Gap\nI don't know yet. Objectives\nBuild AI.",
        "well_structured": "Abstract\nThe integration of LLMs in academic environments remains understudied. \nResearch Gap\nPrior work has not examined real-time conversational agents in physics. \nObjectives\nRQ1: Does realtime ITS improve physics scores? \nMethodology\nWe will deploy a 6-week study. \nEvaluation\nPre-post tests analyzed via ANOVA. \nLimitations\nSample size is restricted to one school. \nEthics\nAll data is anonymized."
    }

    for name, text in proposals.items():
        print(f"\n================ Testing: {name} ================")
        
        resp_weak = client.post("/predict-weakness", json={"text": text})
        print(f"POST /predict-weakness Status: {resp_weak.status_code}")
        if resp_weak.status_code == 200:
            print(f"Weakness Response Keys: {list(resp_weak.json().keys())}")
        else:
            print(f"Validation Error: {resp_weak.text}")
            
        resp_grade = client.post("/grade-report", json={"text": text, "source": "text", "analysis_id": f"test-{name}"})
        print(f"POST /grade-report Status: {resp_grade.status_code}")
        if resp_grade.status_code == 200:
            js = resp_grade.json()
            print(f"Grade Predicted Score: {js.get('predicted_score')}")
            
        resp_analyze = client.post("/analyze", json={"text": text, "request_id": f"req-{name}", "analysis_id": f"test-{name}", "source": "text"})
        print(f"POST /analyze Status: {resp_analyze.status_code}")
        if resp_analyze.status_code == 200:
            js = resp_analyze.json()
            print(f"Analyze Retrieved Feedback Count: {len(js.get('retrieved_feedback', []))}")

if __name__ == "__main__":
    test_endpoints()
