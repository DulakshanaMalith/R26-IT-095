import sys
import os

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

from main import generate_schedule, ProjectRequest

req = ProjectRequest(
    description=text,
    team_size=4,
    duration_months=6,
    function_points=100,
    start_date="2026-08-30"
)

res = generate_schedule(req)
print(f"Final API Response Total Tasks: {res.total_tasks}")
