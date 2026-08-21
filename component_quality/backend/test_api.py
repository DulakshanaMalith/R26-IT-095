from fastapi.testclient import TestClient
from src.api.main import app
import json

client = TestClient(app)

PROPOSAL_TEXT = """
Abstract
This proposal introduces a novel system for monitoring battery impact and latency in child wearables using MobileNetV2 and TFLite. 
We address the research problem of balancing accuracy limitations with device constraints.
Objectives
The goal is to evaluate the system against baseline datasets such as SaveeTess. We aim to achieve recall > 90%, FAR < 5%, latency <= 2 seconds, and battery impact < 10%.
Methodology
We employ Resemblyzer for Speaker Verification and measure Distress levels.
Future Work
Future extensions include deployment in real-world scenarios, outside the scope of the current project.
"""

response = client.post("/api/supervisor/analyze", json={
    "proposal_text": PROPOSAL_TEXT,
    "student_id": "test",
    "student_name": "test",
    "proposal_title": "test"
})
print("STATUS CODE:", response.status_code)
if response.status_code == 200:
    data = response.json()
    kg = data.get("knowledge_graph", {})
    print("IMPLICIT CONCEPTS in API:", kg.get("implicit_concepts"))
    print("MISSING CONCEPTS in API:", kg.get("missing_concepts"))
else:
    print("ERROR:", response.text)
