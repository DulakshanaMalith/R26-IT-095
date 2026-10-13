"""Generate reusable scheduling and progress-tracking demonstration data.

Run from the component_scheduling directory:
    python generate_test_data_pack.py
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "test_data_pack"
PROPOSAL_DIR = OUTPUT / "proposals"
ACADEMIC_DIR = OUTPUT / "academic_scheduler"
EVIDENCE_DIR = OUTPUT / "progress_evidence_R26-IT-095"
DOCUMENT_DIR = EVIDENCE_DIR / "submission_documents"
REPO_DIR = EVIDENCE_DIR / "github_repo_R26-IT-095"
WEBHOOK_DIR = EVIDENCE_DIR / "webhook_payloads"

PROJECT_ID = "R26-IT-095"
GITHUB_REPOSITORY = "ModithaDilshan/test-repo"
SOURCE_PDF = ROOT / "Proposal Reort Merged Final (1) (1).pdf"

SOURCE_TASKS = [
    "Gantt Chart",
    "Literature Review",
    "Automated and Constraint-Based Team Formation",
    "Semantic Skill Profiling with Sentence Transformers",
    "Multi-Objective Optimization for Team Composition",
    "Predictive Modelling for Educational Outcomes",
    "Existing Tools and Their Limitations",
    "Objectives",
    "Technical Methods and Algorithms",
    "Tools and Platforms",
    "Component Overview",
    "User Requirements",
    "Functional Requirements",
    "Target Market and Customer Persona",
    "Value Proposition",
    "Work Breakdown Structure (WBS)",
    "Project Initiation and Ethics Clearance",
    "Data Collection and Historical Outcome Preparation",
    "SBERT Skill Profiling",
    "NSGA-II Optimization",
    "XGBoost Feasibility Prediction",
    "Cold-Start Skill-Gap Analysis",
    "Dashboard Implementation",
    "IPMS API Integration",
    "System Integration and End-to-End Testing",
    "Pilot Study and Supervisor Evaluation",
    "Report Writing and Thesis Preparation",
]

PROPOSALS = [
    {
        "group_id": "R26-IT-101",
        "title": "Intelligent Hospital Appointment and Patient Flow Platform",
        "domain": "digital health, queue prediction, appointment scheduling, and clinical operations",
        "members": ["IT22120001", "IT22120002", "IT22120003", "IT22120004"],
        "tasks": [
            "Conduct Digital Health Literature Review",
            "Conduct Stakeholder Requirements Workshop",
            "Define Patient Privacy and Consent Requirements",
            "Prepare Functional Requirements Specification",
            "Design Patient Journey and Service Blueprint",
            "Design Accessible Patient Portal Interfaces",
            "Model Hospital Appointment Domain Architecture",
            "Design Secure Clinical Database Schema",
            "Implement Role-Based Authentication Service",
            "Implement Patient Registration Workflow",
            "Develop Doctor Availability Management Module",
            "Develop Appointment Booking and Cancellation Service",
            "Build Real-Time Patient Queue Management Engine",
            "Engineer Queue Waiting-Time Prediction Features",
            "Train Waiting-Time Prediction Model",
            "Develop SMS and Email Notification Service",
            "Integrate Hospital Scheduling REST API",
            "Implement Operations Monitoring Dashboard",
            "Perform Unit and Integration Testing",
            "Conduct Security and Privacy Validation",
            "Run Performance and Load Evaluation",
            "Deploy Containerized Pilot Environment",
            "Conduct Hospital User Acceptance Pilot",
            "Evaluate Prediction Accuracy and Usability",
            "Prepare Final Technical Report and User Manual",
        ],
    },
    {
        "group_id": "R26-IT-102",
        "title": "AI-Enabled Smart Campus Energy Optimization System",
        "domain": "IoT energy monitoring, demand forecasting, anomaly detection, and sustainability",
        "members": ["IT22120101", "IT22120102", "IT22120103", "IT22120104"],
        "tasks": [
            "Review Smart Energy Management Research",
            "Analyze Campus Building Energy Operations",
            "Define Sustainability and Data Requirements",
            "Prepare IoT Sensor Deployment Plan",
            "Design Energy Data Collection Architecture",
            "Design Time-Series Database Schema",
            "Implement Smart Meter Data Ingestion Gateway",
            "Implement Sensor Data Validation Pipeline",
            "Implement Building and Device Registry",
            "Develop Real-Time Energy Monitoring Dashboard",
            "Engineer Weather and Occupancy Features",
            "Train Short-Term Demand Forecasting Model",
            "Build Energy Anomaly Detection Service",
            "Develop Peak-Demand Alert Workflow",
            "Implement Energy Recommendation Engine",
            "Integrate External Weather and Timetable Data Sources",
            "Develop Sustainability Reporting Module",
            "Perform Sensor Pipeline Integration Testing",
            "Validate Forecasting Model Accuracy",
            "Conduct Cybersecurity and Access Review",
            "Run Streaming Performance Evaluation",
            "Deploy Campus Pilot Infrastructure",
            "Conduct Facilities Team Acceptance Pilot",
            "Measure Energy-Saving Intervention Outcomes",
            "Prepare Deployment Guide and Final Research Report",
        ],
    },
    {
        "group_id": "R26-IT-103",
        "title": "Traceable Agricultural Marketplace and Crop Advisory Platform",
        "domain": "agritech, produce traceability, market-price analytics, and crop advisory",
        "members": ["IT22120201", "IT22120202", "IT22120203", "IT22120204"],
        "tasks": [
            "Review Digital Agriculture and Traceability Research",
            "Interview Farmers Buyers and Agricultural Officers",
            "Define Marketplace and Traceability Requirements",
            "Design Multilingual Farmer Experience",
            "Model Produce Supply-Chain Architecture",
            "Design Farmer Crop and Transaction Database",
            "Implement Farmer Identity and Access Module",
            "Develop Crop Listing and Inventory Service",
            "Develop Buyer Ordering and Payment Workflow",
            "Implement QR-Based Produce Traceability",
            "Build Market Price Data Collection Pipeline",
            "Engineer Crop and Regional Price Features",
            "Train Market Price Forecasting Model",
            "Develop Crop Advisory Recommendation Engine",
            "Integrate Weather Forecasting Service",
            "Implement Logistics Coordination Module",
            "Develop Farmer and Officer Analytics Dashboard",
            "Perform Marketplace Integration Testing",
            "Validate Traceability Record Integrity",
            "Evaluate Forecast and Recommendation Accuracy",
            "Conduct Mobile Accessibility and Language Testing",
            "Deploy Regional Pilot Environment",
            "Conduct Farmer and Buyer Acceptance Pilot",
            "Analyze Pilot Adoption and Outcome Metrics",
            "Prepare User Guides and Final Evaluation Report",
        ],
    },
]


def ensure_directories() -> None:
    for path in (PROPOSAL_DIR, ACADEMIC_DIR, DOCUMENT_DIR, REPO_DIR, WEBHOOK_DIR):
        path.mkdir(parents=True, exist_ok=True)


def pdf_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Title"], fontSize=24,
                              leading=30, alignment=TA_CENTER, textColor=colors.HexColor("#183B63")))
    styles.add(ParagraphStyle(name="CoverMeta", parent=styles["Normal"], fontSize=11,
                              leading=17, alignment=TA_CENTER, textColor=colors.HexColor("#4C627A")))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading1"], fontSize=16,
                              leading=20, spaceBefore=10, spaceAfter=8,
                              textColor=colors.HexColor("#175A9C")))
    styles.add(ParagraphStyle(name="Task", parent=styles["Normal"], fontSize=9.5,
                              leading=13, leftIndent=5 * mm, spaceAfter=2))
    return styles


def add_page_number(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#6B7F93"))
    canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, f"Page {doc.page}")
    canvas.restoreState()


def create_proposal_pdf(proposal: dict) -> Path:
    path = PROPOSAL_DIR / f"{proposal['group_id']}_Test_Proposal.pdf"
    styles = pdf_styles()
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            title=proposal["title"], author=proposal["group_id"])
    story = [Spacer(1, 28 * mm), Paragraph(proposal["title"], styles["CoverTitle"]),
             Spacer(1, 8 * mm), Paragraph(f"Project Proposal Report<br/>{proposal['group_id']}", styles["CoverMeta"]),
             Spacer(1, 7 * mm), Paragraph("Team Members<br/>" + "<br/>".join(proposal["members"]), styles["CoverMeta"]),
             Spacer(1, 10 * mm), Paragraph("BSc (Hons) Information Technology<br/>Test Data for IPMS Adaptive Scheduling", styles["CoverMeta"]),
             PageBreak(), Paragraph("1. Abstract", styles["Section"]),
             Paragraph(f"This project proposes a research-driven platform for {proposal['domain']}. "
                       "The study combines requirements engineering, secure software development, "
                       "model evaluation, usability assessment, and a controlled pilot deployment. "
                       "The work packages below are explicit executable tasks for scheduling tests.", styles["BodyText"]),
             Paragraph("2. Specific Objectives", styles["Section"]),
             Paragraph("SO1: Design and implement a secure, usable end-to-end platform for the selected domain.", styles["BodyText"]),
             Paragraph("SO2: Develop and evaluate data-driven decision-support capabilities using measurable evidence.", styles["BodyText"]),
             Paragraph("SO3: Validate technical performance and stakeholder usability through a documented pilot study.", styles["BodyText"]),
             Paragraph("3. Methodology", styles["Section"]),
             Paragraph("The team will follow an iterative research methodology covering discovery, design, implementation, testing, deployment, and evaluation. Each task has a tangible deliverable and can be assigned independently or collaboratively.", styles["BodyText"]),
             Paragraph("4. Work Breakdown Structure (WBS)", styles["Section"])]
    for index, task in enumerate(proposal["tasks"], 1):
        story.append(Paragraph(f"{index}. {task}", styles["Task"]))
    story.extend([Paragraph("GANTT CHART", styles["Section"]),
                  Paragraph("The detailed dates and resource assignments will be generated by the IPMS dependency-aware scheduler after proposal upload.", styles["BodyText"]),
                  Paragraph("EXPECTED OUTCOMES", styles["Section"]),
                  Paragraph("Expected outputs include a validated prototype, traceable research evidence, model evaluation results, stakeholder feedback, deployment documentation, and a final research report.", styles["BodyText"])])
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return path


THIN = Side(style="thin", color="B7C9DB")
CELL_BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def style_sheet(ws, widths: list[int], header_color: str, alternating: tuple[str, str]) -> None:
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    ws.row_dimensions[1].height = 34
    for cell in ws[1]:
        cell.fill = PatternFill("solid", fgColor=header_color)
        cell.font = Font(color="FFFFFF", bold=True, size=10)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = CELL_BORDER
    for row_index in range(2, ws.max_row + 1):
        fill = PatternFill("solid", fgColor=alternating[row_index % 2])
        for cell in ws[row_index]:
            cell.fill = fill
            cell.border = CELL_BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        ws.row_dimensions[row_index].height = 34
    for index, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(index)].width = width


def create_academic_workbooks() -> tuple[Path, Path]:
    dates = ",".join([
        "2026-09-08", "2026-09-09", "2026-09-10",
        "2026-10-20", "2026-10-21", "2026-10-22",
        "2026-12-01", "2026-12-02", "2026-12-03",
        "2027-01-12", "2027-01-13", "2027-01-14",
    ])
    first_names = ["Aarav", "Amaya", "Nimal", "Kavindi", "Ruwan", "Tharushi", "Dinesh", "Ishara", "Malith", "Nethmi",
                   "Kasun", "Dinithi", "Sahan", "Piumi", "Lakshan", "Shenali", "Ravindu", "Sachini", "Dilshan", "Harini",
                   "Chamod", "Ayesha", "Gayan", "Imesha", "Supun", "Nadeesha", "Thilina", "Madhavi", "Akila", "Sanduni"]
    last_names = ["Perera", "Silva", "Fernando", "Jayasinghe", "Wijesinghe", "De Silva", "Rathnayake", "Gunawardena", "Senanayake", "Karunaratne"]
    roles = ["Professor"] * 8 + ["Doctor"] * 8 + ["Lecturer"] * 7 + ["Instructor"] * 7
    expertise = [
        "machine learning, deep learning, predictive analytics, data science",
        "software engineering, project management, agile methods, DevOps",
        "natural language processing, information retrieval, generative AI",
        "cybersecurity, privacy engineering, network security, authentication",
        "database systems, cloud computing, distributed systems, big data",
        "human computer interaction, UX research, accessibility, mobile systems",
        "optimization, operations research, scheduling, evolutionary algorithms",
        "IoT, embedded systems, sensor analytics, smart environments",
        "computer vision, image processing, pattern recognition, deep learning",
        "research methods, statistics, educational technology, evaluation",
    ]
    supervisor_path = ACADEMIC_DIR / "panel_members_30.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Supervisors"
    ws.append(["Name", "Email", "Expertise / Research Areas",
               "Available Dates (YYYY-MM-DD, comma separated)",
               "Available Times (HH:MM-HH:MM)",
               "Role (Professor/Doctor/Lecturer/Instructor)"])
    for index, first in enumerate(first_names):
        last = last_names[index % len(last_names)]
        prefix = "Prof." if roles[index] == "Professor" else ("Dr." if roles[index] == "Doctor" else ("Mr." if index % 2 == 0 else "Ms."))
        ws.append([f"{prefix} {first} {last}", f"{first.lower()}.{last.lower().replace(' ', '')}@ipms-test.edu.lk",
                   expertise[index % len(expertise)], dates, "08:00-18:00", roles[index]])
    style_sheet(ws, [24, 34, 58, 78, 28, 35], "175A9C", ("E8F3FC", "F6FAFE"))
    wb.save(supervisor_path)

    hall_path = ACADEMIC_DIR / "hall_locations_8.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Halls"
    ws.append(["Hall Name", "Capacity", "Floor / Building",
               "Available Dates (YYYY-MM-DD, comma separated)",
               "Available Times (HH:MM-HH:MM)"])
    halls = [
        ("Innovation Auditorium", 180, "Ground Floor, Innovation Centre"),
        ("Computing Hall A", 90, "1st Floor, Computing Building"),
        ("Computing Hall B", 80, "2nd Floor, Computing Building"),
        ("Research Seminar Room 1", 45, "3rd Floor, Research Wing"),
        ("Research Seminar Room 2", 45, "3rd Floor, Research Wing"),
        ("Smart Classroom C201", 60, "2nd Floor, Academic Block C"),
        ("Engineering Lecture Theatre", 120, "Ground Floor, Engineering Block"),
        ("Library Collaboration Hall", 70, "1st Floor, Main Library"),
    ]
    for hall in halls:
        ws.append([hall[0], hall[1], hall[2], dates, "08:00-18:00"])
    style_sheet(ws, [30, 12, 38, 78, 28], "087F5B", ("E8F8F2", "F5FCF9"))
    wb.save(hall_path)
    return supervisor_path, hall_path


def create_evidence_pdf(path: Path, title: str, task_id: int, author: str, sections: list[tuple[str, str]]) -> None:
    styles = pdf_styles()
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            title=title, author=author)
    story = [Paragraph(title, styles["CoverTitle"]), Spacer(1, 4 * mm),
             Paragraph(f"{PROJECT_ID}-TASK-{task_id:03d}<br/>Submitted by {author}<br/>Supervisor Review Sample", styles["CoverMeta"]),
             Spacer(1, 8 * mm)]
    for heading, body in sections:
        story.extend([Paragraph(heading, styles["Section"]), Paragraph(body, styles["BodyText"]), Spacer(1, 3 * mm)])
    story.append(Paragraph("Declaration", styles["Section"]))
    story.append(Paragraph("This demonstration document is synthetic test evidence created for IPMS progress-tracking validation. It contains no real participant data.", styles["BodyText"]))
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)


def create_evidence_docx(path: Path, title: str, task_id: int, author: str,
                         sections: list[tuple[str, str]]) -> None:
    document = Document()
    heading = document.add_heading(title, 0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta = document.add_paragraph(f"{PROJECT_ID}-TASK-{task_id:03d}\nSubmitted by {author}\nSupervisor Review Sample")
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for section, body in sections:
        document.add_heading(section, level=1)
        document.add_paragraph(body)
    document.add_heading("Submission Declaration", level=1)
    document.add_paragraph("Synthetic demonstration evidence for IPMS progress-tracking tests. No real participants or confidential information are included.")
    document.save(path)


def create_submission_documents() -> dict[int, Path]:
    documents: dict[int, Path] = {}
    documents[2] = DOCUMENT_DIR / "R26-IT-095_TASK-002_Literature_Review.pdf"
    create_evidence_pdf(documents[2], "Literature Review: Intelligent Project Management", 2, "All Members", [
        ("Review Scope", "The review examines automated team formation, semantic skill profiling, multi-objective optimization, workload balancing, schedule risk prediction, and evidence-based progress tracking."),
        ("Search Strategy", "Peer-reviewed studies were grouped by method, dataset, objective function, evaluation design, and reported limitations. Evidence was compared using a structured literature matrix."),
        ("Research Gap", "Existing approaches commonly optimize one stage in isolation. The proposed work studies an integrated workflow combining explainable assignment, scheduling, academic-event planning, and verified progress evidence."),
        ("Conclusion", "The findings motivate a modular IPMS design with measurable optimization outcomes, auditable task evidence, and human approval for high-impact decisions."),
    ])
    documents[12] = DOCUMENT_DIR / "R26-IT-095_TASK-012_User_Requirements.docx"
    create_evidence_docx(documents[12], "User Requirements Specification", 12, "IT22101624", [
        ("Supervisor Requirements", "Upload proposals, inspect extracted tasks, generate schedules, review workload balance, inspect evidence, and approve or reject student document submissions."),
        ("Academic Staff Requirements", "Upload panel and hall availability, schedule all eligible groups, detect staff and hall conflicts, revise events, and export timetables."),
        ("Student Integration Requirements", "View assigned document tasks through the standalone submission portal and upload supported evidence without receiving staff-dashboard access."),
        ("Quality Attributes", "The system shall provide role-based access, traceable decisions, responsive interfaces, deterministic validation, and persistent PostgreSQL storage."),
    ])
    documents[13] = DOCUMENT_DIR / "R26-IT-095_TASK-013_Functional_Requirements.docx"
    create_evidence_docx(documents[13], "Functional Requirements and Acceptance Criteria", 13, "IT22114662", [
        ("FR-01 Proposal Processing", "The system shall extract a group identifier and evidence-backed WBS tasks from an uploaded PDF. Acceptance: the identifier is populated and every task retains source evidence."),
        ("FR-02 Workload Assignment", "The system shall assign individual tasks only during workload balancing while retaining collaborative tasks for all members. Acceptance: assignment totals and balance metrics are reproducible."),
        ("FR-03 Academic Events", "The system shall allocate exactly two Professor/Doctor members, one Lecturer, one Instructor, and one available hall without time conflicts."),
        ("FR-04 Progress Evidence", "The system shall connect explicit task references in commits and documents to the correct task and require supervisor review before document completion."),
        ("FR-05 Auditability", "The system shall store schedule versions separately from progress events and retain reviewer decisions with timestamps and comments."),
    ])
    documents[26] = DOCUMENT_DIR / "R26-IT-095_TASK-026_Pilot_Study.pdf"
    create_evidence_pdf(documents[26], "Pilot Study and Supervisor Evaluation", 26, "All Members", [
        ("Pilot Design", "A controlled demonstration used three synthetic proposals, thirty panel members, eight halls, four team members, document submissions, and task-referenced Git commits."),
        ("Scenarios", "Participants generated schedules, balanced workload, opened schedule history, scheduled Proposal/PP1/PP2/Viva events, submitted evidence, and performed supervisor review."),
        ("Observed Results", "Core workflows completed without conflicting panel, hall, or time allocations. Explicit task references were linked while unmatched evidence remained visible for review."),
        ("Recommended Improvements", "Future evaluation should include additional institutions, longitudinal student activity, comparison baselines, and formal usability instruments."),
    ])
    documents[27] = DOCUMENT_DIR / "R26-IT-095_TASK-027_Final_Report_Draft.pdf"
    create_evidence_pdf(documents[27], "Final Project Report Draft", 27, "All Members", [
        ("System Overview", "The IPMS prototype combines proposal-to-WBS extraction, dependency-aware scheduling, workload optimization, academic-event scheduling, semantic quality assessment, risk monitoring, and team formation."),
        ("Technical Contribution", "The scheduling component separates plan versions from verified progress evidence and combines document review with task-referenced repository activity."),
        ("Evaluation Summary", "Synthetic integration scenarios verify parser coverage, role-constrained panels, conflict prevention, schedule persistence, workload reporting, and progress evidence handling."),
        ("Limitations", "The demonstration dataset is synthetic, GitHub evidence requires webhook configuration, and institutional deployment requires SSO and data-governance approval."),
        ("Conclusion", "The component is suitable as a research prototype when claims are presented with baselines, ablation studies, reproducible datasets, and clearly identified limitations."),
    ])
    return documents


def run_git(*args: str, env: dict | None = None) -> str:
    completed = subprocess.run(["git", *args], cwd=REPO_DIR, env=env, check=True,
                               capture_output=True, text=True)
    return completed.stdout.strip()


def create_git_repository() -> list[dict]:
    if (REPO_DIR / ".git").exists():
        raise RuntimeError(f"Refusing to overwrite existing Git repository: {REPO_DIR}")
    run_git("init", "-b", "main")
    run_git("config", "user.name", "IPMS Test Team")
    run_git("config", "user.email", "ipms-test@example.invalid")
    authors = [
        ("Dilan Perera", "dilan.dev@example.invalid", "dilan-dev", "IT22114662"),
        ("Nethmi Silva", "nethmi.ai@example.invalid", "nethmi-ai", "IT22117014"),
        ("Kasun Fernando", "kasun.ml@example.invalid", "kasun-ml", "IT22109576"),
        ("Amaya Jayasinghe", "amaya.ui@example.invalid", "amaya-ui", "IT22101624"),
    ]
    files_and_commits = [
        ("README.md", "# R26-IT-095 Progress Evidence Test Repository\n\nSynthetic code repository for the IPMS progress-tracking demonstration. Commit messages contain explicit task keys recognized by the scheduling backend.\n", 9, "Document technical methods and repository workflow"),
        ("src/team_formation.py", "def form_team(candidates, team_size=4):\n    return sorted(candidates, key=lambda item: item.get('skill_score', 0), reverse=True)[:team_size]\n", 3, "Implement constraint-based team formation baseline"),
        ("src/semantic_profile.py", "def cosine_similarity(vector_a, vector_b):\n    dot = sum(a*b for a,b in zip(vector_a, vector_b))\n    return dot / ((sum(a*a for a in vector_a) ** 0.5) * (sum(b*b for b in vector_b) ** 0.5) or 1)\n", 4, "Add semantic skill similarity calculation"),
        ("src/optimizer.py", "OBJECTIVES = ('skill_coverage', 'preference', 'workload_balance')\n\ndef objective_vector(solution):\n    return tuple(solution.get(name, 0.0) for name in OBJECTIVES)\n", 5, "Define NSGA-II team composition objectives"),
        ("src/outcome_model.py", "FEATURES = ['team_skill', 'workload', 'task_complexity', 'completion_rate']\n\ndef prepare_features(record):\n    return [float(record.get(name, 0)) for name in FEATURES]\n", 6, "Prepare educational outcome prediction features"),
        ("src/sbert_service.py", "class SkillProfileService:\n    def encode(self, skills):\n        return {'skills': sorted(set(s.lower().strip() for s in skills if s.strip()))}\n", 19, "Build SBERT profiling service contract"),
        ("src/nsga_scheduler.py", "def rank_tradeoffs(candidates):\n    return sorted(candidates, key=lambda item: (item['delay'], item['imbalance'], -item['confidence']))\n", 20, "Implement deterministic trade-off ranking"),
        ("src/feasibility.py", "def feasibility_features(effort, capacity, dependencies):\n    return {'effort': effort, 'capacity_ratio': effort / max(capacity, 1), 'dependencies': len(dependencies)}\n", 21, "Add XGBoost feasibility feature engineering"),
        ("src/cold_start.py", "def least_loaded_member(loads):\n    return min(loads, key=lambda member: (loads[member], member))\n", 22, "Implement cold-start least-loaded assignment"),
        ("web/dashboard.js", "export function progressLabel(value) {\n  return `${Math.max(0, Math.min(100, value))}% verified`;\n}\n", 23, "Add verified progress dashboard formatter"),
        ("api/progress_routes.py", "def task_key(project_id, task_id):\n    return f'{project_id}-TASK-{int(task_id):03d}'\n", 24, "Implement task evidence API key format"),
        ("tests/test_integration.py", "def test_task_reference_format():\n    assert f'R26-IT-095-TASK-{24:03d}' == 'R26-IT-095-TASK-024'\n", 25, "Add end-to-end task reference test"),
    ]
    commit_records = []
    base_date = datetime(2026, 6, 2, 9, 15)
    for index, (relative, content, task_id, summary) in enumerate(files_and_commits):
        target = REPO_DIR / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        run_git("add", relative)
        author = authors[index % len(authors)]
        commit_date = (base_date + timedelta(days=index * 5, hours=index % 4)).isoformat()
        env = os.environ.copy()
        env.update({"GIT_AUTHOR_NAME": author[0], "GIT_AUTHOR_EMAIL": author[1],
                    "GIT_COMMITTER_NAME": author[0], "GIT_COMMITTER_EMAIL": author[1],
                    "GIT_AUTHOR_DATE": commit_date, "GIT_COMMITTER_DATE": commit_date})
        message = f"[{PROJECT_ID}-TASK-{task_id:03d}] {summary}"
        run_git("commit", "-m", message, env=env)
        commit_records.append({"sha": run_git("rev-parse", "HEAD"), "message": message,
                               "timestamp": commit_date, "github_login": author[2],
                               "student_id": author[3], "email": author[1], "task_id": task_id})
    identity_path = REPO_DIR / "GITHUB_IDENTITIES.json"
    identity_path.write_text(json.dumps([
        {"project_id": PROJECT_ID, "student_id": item[3], "github_login": item[2]}
        for item in authors
    ], indent=2), encoding="utf-8")
    run_git("add", identity_path.name)
    identity_date = (base_date + timedelta(days=len(files_and_commits) * 5)).isoformat()
    identity_env = os.environ.copy()
    identity_env.update({"GIT_AUTHOR_NAME": authors[0][0], "GIT_AUTHOR_EMAIL": authors[0][1],
                         "GIT_COMMITTER_NAME": authors[0][0], "GIT_COMMITTER_EMAIL": authors[0][1],
                         "GIT_AUTHOR_DATE": identity_date, "GIT_COMMITTER_DATE": identity_date})
    identity_message = f"[{PROJECT_ID}-TASK-009] Add test GitHub identity mappings"
    run_git("commit", "-m", identity_message, env=identity_env)
    commit_records.append({"sha": run_git("rev-parse", "HEAD"), "message": identity_message,
                           "timestamp": identity_date, "github_login": authors[0][2],
                           "student_id": authors[0][3], "email": authors[0][1], "task_id": 9})
    return commit_records


def create_webhook_payloads(commits: list[dict]) -> None:
    for batch_index in range(0, len(commits), 4):
        batch = commits[batch_index:batch_index + 4]
        payload = {
            "ref": "refs/heads/main",
            "repository": {"full_name": GITHUB_REPOSITORY},
            "pusher": {"name": batch[-1]["github_login"]},
            "commits": [{
                "id": item["sha"], "message": item["message"], "timestamp": item["timestamp"],
                "author": {"name": item["github_login"], "email": item["email"],
                           "username": item["github_login"]},
                "url": f"https://github.com/{GITHUB_REPOSITORY}/commit/{item['sha']}",
            } for item in batch],
            "head_commit": {"id": batch[-1]["sha"], "message": batch[-1]["message"]},
        }
        (WEBHOOK_DIR / f"push_batch_{batch_index // 4 + 1:02d}.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8")


def create_task_manifest(documents: dict[int, Path], commits: list[dict]) -> Path:
    commit_tasks = {item["task_id"] for item in commits}
    path = EVIDENCE_DIR / "R26-IT-095_task_evidence_manifest.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Task Evidence"
    ws.append(["Task ID", "Task Key", "Source Proposal Task", "Expected Evidence",
               "Sample Evidence", "Suggested Student"])
    owners = ["IT22114662", "IT22117014", "IT22109576", "IT22101624"]
    for task_id, task_name in enumerate(SOURCE_TASKS, 1):
        if task_id in documents:
            evidence_type = "DOCUMENT"
            sample = str(documents[task_id].relative_to(OUTPUT))
        elif task_id in commit_tasks:
            evidence_type = "GITHUB COMMIT"
            sample = "github_repo_R26-IT-095 (see matching commit message)"
        else:
            evidence_type = "MANUAL / COLLABORATIVE"
            sample = "No automatic sample; supervisor may verify manually"
        ws.append([task_id, f"{PROJECT_ID}-TASK-{task_id:03d}", task_name,
                   evidence_type, sample, owners[(task_id - 1) % len(owners)]])
    style_sheet(ws, [12, 28, 52, 24, 68, 22], "4C3B8F", ("F0EDFA", "FAF9FD"))
    wb.save(path)
    return path


def create_readme(proposal_paths: list[Path], supervisor_path: Path, hall_path: Path,
                  documents: dict[int, Path], manifest_path: Path) -> None:
    text = f"""# IPMS Scheduling and Progress-Tracking Test Data Pack

Generated synthetic data. It contains no real staff, student, participant, or research data.

## Contents

- `proposals/`: three distinct test proposals; each has 25 explicit WBS tasks.
- `academic_scheduler/{supervisor_path.name}`: 30 panel members (8 Professors, 8 Doctors, 7 Lecturers, 7 Instructors).
- `academic_scheduler/{hall_path.name}`: 8 physical hall locations.
- `progress_evidence_R26-IT-095/submission_documents/`: five task-aligned sample submissions for the supplied source proposal.
- `progress_evidence_R26-IT-095/github_repo_R26-IT-095/`: ready-to-push local Git repository with 13 realistic commits.
- `progress_evidence_R26-IT-095/webhook_payloads/`: sample GitHub push payloads using the repository's real local commit SHAs.
- `{manifest_path.relative_to(OUTPUT)}`: mapping of all 27 source tasks to document, Git, or manual evidence.

## Proposal parser test

Upload each PDF through the scheduling proposal form. The expected Group IDs are R26-IT-101, R26-IT-102, and R26-IT-103. Each file is designed to extract at least 20 tasks. Do not use these synthetic groups as production records.

## Academic-event scheduler test

1. Sign in as Academic Staff.
2. Upload `{supervisor_path.name}` in Step 1 and `{hall_path.name}` in Step 2.
3. Use Project Start Date `2026-09-01` and event weeks Proposal=2, PP1=8, PP2=14, Viva=20.
4. All sample people and halls are available on the matching dates from 08:00 to 18:00.
5. The staff-role distribution supports the required panel: two Professor/Doctor members, one Lecturer, and one Instructor.

Uploading a workbook marks previous staff or halls inactive. Use only in a test database or re-upload your real workbook afterward.

## Document progress test for R26-IT-095

1. Generate and workload-balance the supplied `{SOURCE_PDF.name}` proposal first.
2. Run `run_student_submission_portal.bat` separately and open http://127.0.0.1:8010.
3. Enter Group ID `R26-IT-095` and a student assigned to the selected task.
4. Load document tasks and upload the matching sample file.
5. Review the pending document from the supervisor progress window and approve, request changes, or reject it.

The sample files match the current document-task IDs: 002 Literature Review, 012 User Requirements, 013 Functional Requirements, 026 Pilot Study, and 027 Report Writing. If the proposal parser or schedule is changed later, confirm IDs against the latest Gantt chart and the manifest before uploading.

## Git progress test

The included local repository is connected to `https://github.com/ModithaDilshan/test-repo.git`. If the remote is removed, reconnect it inside the local repository with:

```text
git remote add origin https://github.com/ModithaDilshan/test-repo.git
git push -u origin main
```

Register that HTTPS GitHub URL in the supervisor dashboard. Add all mappings from `GITHUB_IDENTITIES.json`, configure the GitHub webhook secret, and set the webhook URL to `/api/webhooks/github`. GitHub will then deliver future pushes. Existing commits are not automatically replayed by GitHub; make a new task-referenced commit or use the JSON fixtures with a valid HMAC signature in a controlled test.

Recognized format: `[R26-IT-095-TASK-024] message`. A commit is evidence and raises a linked task to at least 10%; it does not automatically prove full completion.
"""
    (OUTPUT / "README.md").write_text(text, encoding="utf-8")


def validate_workbooks(supervisor_path: Path, hall_path: Path) -> None:
    supervisor_wb = load_workbook(supervisor_path, read_only=True, data_only=True)
    supervisor_rows = list(supervisor_wb.active.iter_rows(values_only=True))
    hall_wb = load_workbook(hall_path, read_only=True, data_only=True)
    hall_rows = list(hall_wb.active.iter_rows(values_only=True))
    assert len(supervisor_rows) == 31, "Expected 30 panel members plus header"
    assert len(hall_rows) == 9, "Expected 8 halls plus header"
    roles = [row[5] for row in supervisor_rows[1:]]
    assert roles.count("Professor") >= 2 and roles.count("Doctor") >= 2
    assert roles.count("Lecturer") >= 1 and roles.count("Instructor") >= 1


def main() -> None:
    ensure_directories()
    proposal_paths = [create_proposal_pdf(proposal) for proposal in PROPOSALS]
    supervisor_path, hall_path = create_academic_workbooks()
    documents = create_submission_documents()
    commits = create_git_repository()
    create_webhook_payloads(commits)
    manifest_path = create_task_manifest(documents, commits)
    create_readme(proposal_paths, supervisor_path, hall_path, documents, manifest_path)
    validate_workbooks(supervisor_path, hall_path)
    print(json.dumps({
        "output": str(OUTPUT),
        "proposals": [str(path) for path in proposal_paths],
        "panel_members": 30,
        "halls": 8,
        "submission_documents": len(documents),
        "git_commits": len(commits),
    }, indent=2))


if __name__ == "__main__":
    main()
