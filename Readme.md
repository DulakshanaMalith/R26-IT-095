# IPMS (Integrated Project Management System) - Unified Workspace

Welcome to the **IPMS Master Monorepo**. This repository seamlessly integrates all four core components developed by the team into a single, unified microservices architecture. 

All four components have been visually unified under a premium, dark-mode glassmorphism aesthetic. They operate as independent microservices to prevent dependency conflicts between different AI models.

---

## 🚀 How to Launch the Full System

Because this is a microservices architecture, you will need to open **multiple terminal windows** to start the various backends and frontends.

### 1. Master Dashboard (The Hub)
Once all subsystems are running, you can access the main dashboard by opening the root `index.html` file in your browser. This dashboard provides links to launch all four components.

---

### 2. Adaptive Scheduling (Component 1)
This component handles generative WBS planning and schedule risk analysis.
**Start the Backend & Frontend (FastAPI):**
1. Open a terminal and navigate to the project root:
   ```bash
   cd component_scheduling
   ```
2. Run the FastAPI server:
   ```bash
   python -m uvicorn main:app --host 127.0.0.1 --port 8000
   ```
3. **Access:** `http://127.0.0.1:8000/app`

---

### 3. Quality Assessment (Component 2)
This component handles automated semantic rubric matching and document grading.
**Start the Backend (FastAPI):**
1. Open a new terminal:
   ```bash
   cd component_quality/src/api
   ```
2. Run the server on port 8001:
   ```bash
   python -m uvicorn app:app --host 127.0.0.1 --port 8001
   ```

**Start the Frontend (React):**
1. Open a new terminal:
   ```bash
   cd component_quality/frontend
   ```
2. Install dependencies (first time only) and start:
   ```bash
   npm install
   npm start
   ```
3. **Access:** `http://127.0.0.1:3000`

---

### 4. Risk Monitoring (Component 3)
This component handles predictive contribution analytics and real-time risk detection.
**Start the Backend & Frontend (Flask):**
1. Open a new terminal:
   ```bash
   cd component_risk/ipms-risk-app
   ```
2. Run the Flask application on port 5000:
   ```bash
   python main.py
   ```
3. **Access:** `http://127.0.0.1:5000`

---

### 5. Team Formation & Topic Feasibility (Component 4)

This component provides academic staff with intelligent decision support for
undergraduate project team formation and topic technical feasibility analysis.

The system validates cohort workbooks, applies a Heuristic-Seeded NSGA-II V3
multi-objective optimizer to generate Pareto team-allocation alternatives, and
allows staff to compare technical requirement coverage against student project
preference satisfaction.

It also provides a deterministic Topic Technical Feasibility module for
evaluating an existing team against the technical requirements of a selected
project/topic.

**Start the Backend (FastAPI):**

1. Open a new terminal:

   ```bash
   cd "component_team/intelligent-team-formation-and-topic-feasiblity-analyzis/backend-fastapi"

## 🎨 Global UI Theme
To ensure visual consistency for the final presentation, all React and Flask frontends have been injected with a `global-theme.css` override. This automatically forces all components to adopt the unified dark space theme without modifying their underlying frontend logic.

## ⚠️ Important Networking Note for Windows Users
If you experience database connection issues or `404 Not Found` errors between the React frontends and Python backends, ensure you are running the backends strictly on `--host 127.0.0.1` rather than `localhost`. This prevents IPv6 loopback collisions on Windows machines.
