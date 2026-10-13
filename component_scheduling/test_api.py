import requests
import json

text = """
INTELLIGENT PROJECT MANAGEMENT SYSTEM FOR UNDERGRADUATE STUDENTS
R26-IT-095 Project Proposal Report BSc. (Hons) Degree in Information Technology, Specializing in Information Technology
Department of Information Technology Sri Lanka Institute of Information Technology Sri Lanka
Supervisor: Prof. Samantha Rajapakshe

GANTT CHART
M1 Requirement Analysis
M2 System Design
M3 Implementation Phase 1
M4 Implementation Phase 2
M5 Integration and Testing
M6 Final Evaluation

Specific Objective 1: To develop an intelligent workload balancing module using Machine Learning.
Specific Objective 2: To create an automated WBS extraction component using NLP.
Specific Objective 3: To design an adaptive UI dashboard for real-time risk alerts.
Specific Objective 4: To integrate automated code review metrics into the risk model.
"""

payload = {
    "description": text,
    "team_size": 4,
    "duration_months": 6,
    "function_points": 100,
    "start_date": "2026-08-30"
}

resp = requests.post("http://127.0.0.1:8000/api/schedule/generate", json=payload)
data = resp.json()

print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    print(f"Total Tasks: {data.get('total_tasks')}")
    print(f"Schedule Length: {len(data.get('schedule', []))}")
    for i, t in enumerate(data.get('schedule', [])):
        print(f"  {i+1}: {t['task_name']} ({t.get('component_owner', 'N/A')})")
else:
    print(f"Error: {resp.text}")
