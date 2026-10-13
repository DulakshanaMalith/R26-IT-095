import sys
import os

# Mock the models dictionary before importing main
import main
from main import extract_wbs_tasks

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

tasks = extract_wbs_tasks(text)
print(f"Extracted tasks: {len(tasks)}")
for t in tasks:
    print("-", t["name"])
