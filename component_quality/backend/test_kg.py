from src.core.knowledge_graph import analyze_knowledge_graph
import json

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

result = analyze_knowledge_graph(PROPOSAL_TEXT)

print("METRICS STATUS: ", "PRESENT" if "Metrics" in result.get("concept_evidence", {}) else "IMPLICIT" if "Metrics" in result.get("implicit_concepts", []) else "MISSING")
print("METRICS EVIDENCE: ", result.get("concept_evidence", {}).get("Metrics", "None"))
print("\nRESEARCH QUESTION STATUS: ", "PRESENT" if "Research Question" in result.get("concept_evidence", {}) else "IMPLICIT" if "Research Question" in result.get("implicit_concepts", []) else "MISSING")
print("RESEARCH QUESTION EVIDENCE: ", result.get("concept_evidence", {}).get("Research Question", "None"))
print("\nLIMITATIONS STATUS: ", "PRESENT" if "Limitations" in result.get("concept_evidence", {}) else "IMPLICIT" if "Limitations" in result.get("implicit_concepts", []) else "MISSING")
print("LIMITATIONS EVIDENCE: ", result.get("concept_evidence", {}).get("Limitations", "None"))
print("\nFUTURE WORK STATUS: ", "PRESENT" if "Future Work" in result.get("concept_evidence", {}) else "IMPLICIT" if "Future Work" in result.get("implicit_concepts", []) else "MISSING")
print("FUTURE WORK EVIDENCE: ", result.get("concept_evidence", {}).get("Future Work", "None"))
print("\nMISSING CONCEPTS: ", result.get("missing_concepts", []))
print("IMPLICIT CONCEPTS: ", result.get("implicit_concepts", []))
print("\nMAIN CONCEPTS: ", result.get("concepts", []))
print("EDGES: ", len(result.get("edges", [])))
