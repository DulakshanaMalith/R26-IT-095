# Generative Project Planning and Adaptive Scheduling
**Component for Integrated Project Management System (IPMS)**

## 📌 Project Overview
This project is an advanced, AI-driven backend module that replaces traditional, manual project scheduling tools (like Jira or MS Project). Instead of requiring users to manually create tasks and guess deadlines, this system uses an intelligent **Multi-Model Machine Learning Pipeline** to automatically read unstructured academic PDF proposals, generate a Work Breakdown Structure (WBS), estimate realistic effort, and probabilistically flag schedule risks before they happen.

It features a **Closed-Loop Adaptive Engine** that integrates with external tools (like GitHub) to track real-time progress, calculate velocity, and autonomously recalculate schedules using Bidirectional Earliest Deadline First (BEDF) algorithms.

---

## 🚀 The 5 Core Novelties (Research Contributions)

This project introduces five distinct research novelties to academic project management:

### 1. Automated WBS Extraction (T5 NLP Pipeline)
*   **The Problem:** Existing tools require project managers to manually type out every task.
*   **The Novelty:** The system features a fine-tuned **T5 Transformer model** that uses dynamic multi-chunk sampling to "read" unstructured, 40+ page academic PDF proposals. It automatically filters out academic noise (like "Literature Review" and "References") and extracts only the actionable implementation deliverables, automatically constructing the Work Breakdown Structure.

### 2. Lifecycle-Aware Effort Estimation (XGBoost)
*   **The Problem:** Traditional schedule generation gives uniform, identical durations to all tasks, failing to account for the SDLC (Software Development Life Cycle).
*   **The Novelty:** An **XGBoost Machine Learning model** predicts the *total* project effort based on Function Points and Team Size. A custom **Lifecycle Effort Weighting Curve** then mathematically distributes those hours across the tasks based on their phase (e.g., "Backend Development" receives a heavier mathematical weight than "Documentation").

### 3. Capacity-Aware Probabilistic Risk Flagging (Logistic Regression)
*   **The Problem:** Static tools only flag a task as "delayed" *after* the deadline is missed.
*   **The Novelty:** A hybrid risk engine blends a **Logistic Regression model** (trained on enterprise Jira data) with a custom **Capacity Ratio Algorithm**. It calculates the precise working hours the team has available and outputs a probabilistic delay risk percentage. Tasks are flagged as `⚠️ HIGH RISK` *before* the project starts if the estimated effort exceeds the real-world team capacity.

### 4. Cross-Module Automated Inactivity Signaling (GitHub Webhooks)
*   **The Problem:** Teams forget to update their scheduling dashboards, leading the system to falsely assume they are delayed (Ghost Teams).
*   **The Novelty:** A **Semantic Task Matching Algorithm** intercepts live GitHub webhooks when code is pushed. It uses sequence matching to map the commit message (e.g., *"finished the login database"*) to the predicted WBS tasks (e.g., *"Backend Development"*). The system logs task completion automatically without manual UI interaction.

### 5. Schedule Drift Analytics (Persistent Version Tracking)
*   **The Problem:** When schedules are updated in traditional tools, old deadlines are overwritten, destroying the historical record of *how* the project failed.
*   **The Novelty:** The adaptive scheduler writes every recalculated schedule version into a persistent **SQLite Database**. This creates an immutable timeline of schedule adaptations, enabling supervisors to perform "Schedule Drift Analytics" by comparing the AI's Day 1 baseline against the reality of Week 10.

---

## ⚙️ System Architecture

### 1. The Machine Learning Pipeline
The FastAPI backend serves three models sequentially:
1.  **HuggingFace T5-Small** -> Extracts the WBS.
2.  **XGBoost Regressor** -> Predicts effort durations.
3.  **Scikit-Learn Logistic Regression** -> Predicts failure probability.

### 2. The Adaptive "Auto-Rescheduling" Loop (BEDF)
When the system detects that a task has been completed (via GitHub Webhook or Dashboard):
*   It compares the **Actual Completion Date** against the **Planned Completion Date**.
*   **If Late:** The system triggers the **Parkinson's Tightening Factor**, mathematically compressing the remaining task deadlines by 10% to force the team to catch up.
*   **If Early:** The system triggers **Bidirectional Earliest Deadline First (BEDF)**, pulling all subsequent tasks forward to optimize early completion.

### 3. The Tech Stack
*   **Backend:** FastAPI (Python), SQLite
*   **Machine Learning:** PyTorch, Transformers, XGBoost, Scikit-Learn, Pandas
*   **Frontend:** HTML5, CSS3 (Glassmorphism UI), Vanilla JavaScript
*   **Integration:** REST APIs, GitHub Webhooks

---

## 💻 How to Run Locally

1. **Install Dependencies:**
   ```bash
   pip install fastapi uvicorn torch transformers xgboost scikit-learn pandas pdfplumber
   ```

2. **Start the Server:**
   ```bash
   python main.py
   ```
   *Note: This will load the 3 ML models into memory and start the server on Port 8000.*

3. **Access the Dashboard:**
   Open your browser and navigate to: `http://localhost:8000`

4. **Testing the Automation (Webhook Simulation):**
   Send a POST request via Postman to `http://localhost:8000/api/webhooks/github` with a mock commit payload to watch the semantic matching and BEDF rescheduling happen in real-time!
