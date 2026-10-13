# IPMS — Extended Research Novelties (6–11)
**Generative Project Planning and Adaptive Scheduling**
*Suggested additions to strengthen the research contribution*

---

## Overview

The five original novelties each work in isolation. The six additions below address the gaps a supervisor will probe: the system does not get smarter over time, does not explain its decisions, does not optimize competing goals simultaneously, ignores team health signals, cannot reason about what-if scenarios, and treats every project as a silo. Each addition below directly extends an existing novelty rather than introducing an unconnected feature.

---

## Novelty 6 — Federated Learning for Cross-Team Effort Estimation

### Category
Machine Learning / Privacy-Preserving AI

### The Problem It Solves
Your XGBoost effort estimator (Novelty 2) is trained on data from one project at a time. A model trained on a single project has high bias — it overfits to that team's speed, domain, and tech stack. This is the **cold-start problem**: a new team gets poor effort predictions because the model has never seen a project like theirs.

Traditional ML requires all training data in one place. Academic project data is sensitive — supervisors and students do not want raw task logs, performance scores, or delay histories shared across departments.

### The Novelty
You introduce a **privacy-preserving collaborative learning architecture** into academic project scheduling. No existing academic PM tool does this. The novelty is the combination of federated aggregation with your existing Lifecycle Weighting Curve — each local model learns domain-specific weights, and the global model learns universal SDLC patterns.

### How It Works — Step by Step

1. **Local training:** Each team's FastAPI instance trains the XGBoost model on its own project data only — task durations, function points, team size, delay outcomes.

2. **Gradient extraction:** Instead of sending raw data, the system extracts only the model's gradient updates (parameter deltas) after each training round.

3. **Federated aggregation:** A central coordinator (Flower framework or PySyft) applies **FedAvg** — it averages the gradients from all participating teams to update the global model.

4. **Global model broadcast:** The improved global model is sent back to all teams. Each team fine-tunes it on their local data before the next prediction cycle.

5. **Differential privacy layer:** Gaussian noise is added to gradients before upload to provide mathematical privacy guarantees (epsilon-delta differential privacy).

### Connection to Existing System
Your XGBoost model (Novelty 2) stays identical — only the training mechanism changes. The Lifecycle Weighting Curve is applied locally after each federated round. No changes are needed to FastAPI endpoints or the frontend dashboard.

### Research Significance
- Addresses the cold-start bias problem in single-team ML models
- First application of federated learning in academic project scheduling tools
- Provides a mathematical privacy guarantee that makes institutional deployment feasible

### Technology Stack
- `flwr` (Flower) — federated learning framework
- `PySyft` — privacy-preserving ML
- XGBoost federated API
- Differential privacy (Gaussian mechanism)
- FedAvg aggregation algorithm

---

## Novelty 7 — Explainable Risk Predictions with SHAP Values

### Category
Explainable AI (XAI)

### The Problem It Solves
Your Logistic Regression model (Novelty 3) outputs a delay risk percentage (e.g. 74%) but gives no reason. A supervisor seeing "74% delay risk" cannot intervene effectively. A black-box risk score creates no trust and no action — this is the gap between ML output and human decision-making.

### The Novelty
You introduce **post-hoc interpretability into automated academic scheduling**. SHAP (SHapley Additive exPlanations) decomposes the risk number into per-feature contributions. The dashboard can then display:

> *"Risk is 74% because team capacity is 41% below estimate (+38%), GitHub velocity dropped last week (+22%), and the task is in Backend Development phase (+14%)."*

SHAP is mathematically grounded in cooperative game theory (Shapley values from economics). Unlike LIME, SHAP guarantees consistency and local accuracy. No academic PM tool currently provides per-task, per-feature risk decomposition to supervisors.

### How It Works — Step by Step

1. **Wrap the Logistic Regression:** After the model predicts risk, pass the same feature vector into `shap.LinearExplainer(model, background_data)`. This is a one-line addition to your existing FastAPI risk endpoint.

2. **Compute SHAP values:** SHAP calculates the marginal contribution of each feature (capacity ratio, velocity trend, phase weight, days remaining) to the final prediction score.

3. **Rank contributions:** Sort features by absolute SHAP value. The top 3 become the "reasons" displayed on the dashboard per task.

4. **Render waterfall chart:** Display a horizontal bar per task — positive SHAP values increase risk (shown in red), negative SHAP values reduce risk (shown in green). This is a SHAP waterfall chart.

5. **Global analysis:** Aggregate SHAP values across all tasks to show supervisors which factors most commonly drive delays in their department — this becomes a publishable research finding about academic project failure patterns.

### Connection to Existing System
Plugs directly into Novelty 3 (Logistic Regression risk engine). The `/api/schedule` response gains a `shap_explanations` field. The glassmorphism dashboard gets one new component per task: the waterfall bar chart. No model retraining is required.

### Research Significance
- Transforms a black-box prediction into an actionable supervisor explanation
- First use of SHAP in academic project scheduling risk systems
- Enables retrospective analysis: which features predicted delays most reliably across all projects

### Technology Stack
- `pip install shap`
- `shap.LinearExplainer` for Logistic Regression models
- Waterfall chart (vanilla JavaScript, frontend)
- FastAPI response schema extension

---

## Novelty 8 — Multi-Objective Pareto-Optimal Schedule Generation

### Category
Optimization / Operations Research

### The Problem It Solves
Your current BEDF scheduler optimizes for a single objective: earliest deadline. Real academic projects involve competing goals that cannot all be maximized simultaneously:
- Minimizing total project duration
- Minimizing team burnout (keeping effort variance low across weeks)
- Maximizing supervisor milestone visibility (ensuring key deliverables appear early)

No existing student project scheduling tool exposes this trade-off to supervisors.

### The Novelty
You introduce **multi-objective evolutionary scheduling** into the BEDF engine. Instead of one optimal schedule, the system generates a **Pareto front** — a set of schedules where no single schedule is better than another in all three objectives at once. Supervisors choose which trade-off fits their priorities.

For example:
- Schedule A: finishes in 10 weeks, high burnout risk, good milestone visibility
- Schedule B: finishes in 12 weeks, low burnout risk, moderate milestone visibility
- Schedule C: finishes in 11 weeks, moderate burnout, excellent milestone visibility

All three are Pareto-optimal. The supervisor selects based on their academic context.

### How It Works — Step by Step

1. **Define the three objective functions:**
   - `f1(schedule)` = total project duration in days
   - `f2(schedule)` = variance of weekly effort hours across the team
   - `f3(schedule)` = weighted sum of milestone tasks appearing in the first 40% of the timeline

2. **Encode schedules as chromosomes:** Each schedule is a permutation of task orderings and deadline offsets — a candidate solution in the search space.

3. **Run NSGA-II (Non-Dominated Sorting Genetic Algorithm):** This evolutionary algorithm evolves a population of schedules over multiple generations, using non-dominated sorting to identify the Pareto front at each generation.

4. **Present the Pareto front:** The dashboard shows 3–5 representative schedules from the Pareto front, each with a radar chart of its three objective scores.

5. **Supervisor selection:** The supervisor clicks their preferred schedule, which becomes the active plan committed to the SQLite version history (Novelty 5).

### Connection to Existing System
Extends the BEDF adaptive scheduler (Novelty 2 + architecture). The Pareto front runs at schedule generation time, before the closed-loop begins. Once a schedule is selected, all existing adaptive logic (Parkinson's Tightening Factor, BEDF pull-forward) operates as normal.

### Research Significance
- First multi-objective optimizer applied to academic SDLC scheduling
- Exposes the burnout-speed-visibility trade-off that all project managers intuitively feel but no tool quantifies
- NSGA-II is a well-established algorithm; applying it to this domain is the contribution

### Technology Stack
- `pymoo` — multi-objective optimization library (NSGA-II)
- `DEAP` — evolutionary algorithms framework (alternative)
- Radar chart component (frontend)
- Extension of existing BEDF scheduler logic

---

## Novelty 9 — Developer Sentiment as a Leading Delay Indicator

### Category
Natural Language Processing / Affective Computing

### The Problem It Solves
Traditional project monitoring tracks only quantitative signals: tasks completed, hours logged, velocity. But delay does not arrive suddenly — it is preceded by qualitative signals in team communication: frustration in commit messages, confusion in PR comments, declining engagement in issue threads.

Your GitHub Webhook integration (Novelty 4) already intercepts these messages but discards the linguistic content after extracting task matches.

### The Novelty
You extend the webhook pipeline with a **fine-tuned sentiment classifier** that runs on every commit message and PR comment. Declining team sentiment over a rolling 7-day window becomes a **leading indicator** of imminent delay — detectable before velocity metrics drop. This is affective computing applied to project risk detection.

Example signal chain:
> Week 5: commits say "added login endpoint" (neutral) → Week 6: "fixed that broken auth again" (mild negative) → Week 7: "why does this keep breaking" (strong negative) → System flags delay risk rising before any deadline is missed.

### How It Works — Step by Step

1. **Fine-tune a sentiment model:** Use a pre-trained `distilbert-base-uncased` model fine-tuned on a software developer corpus (GitHub commit messages, Stack Overflow posts). Label sentiment as Positive / Neutral / Negative / Frustrated.

2. **Integrate into the webhook handler:** In your existing `/api/webhooks/github` endpoint, after semantic task matching, pass the commit message to the sentiment model. Store the score in the SQLite database with a timestamp.

3. **Compute the 7-day sentiment rolling average:** A background task calculates the team's average sentiment score over the last 7 days. A declining trend (slope < threshold) is a leading risk signal.

4. **Combine with the risk engine:** Feed the 7-day sentiment slope as an additional feature into your Logistic Regression model (Novelty 3). This improves prediction accuracy and makes the model sensitive to team health, not just schedule math.

5. **Dashboard alert:** If sentiment drops below a calibrated threshold, the dashboard shows a "Team health warning" alongside the standard risk flag — visible to supervisors, not students (privacy control).

### Connection to Existing System
Extends Novelty 4 (GitHub webhook semantic matching) and Novelty 3 (risk engine). The sentiment score becomes a new feature column in the risk prediction input vector. SQLite schema gains a `sentiment_log` table.

### Research Significance
- First integration of developer affective signals into academic project scheduling risk detection
- Sentiment is a leading indicator (precedes delay); all current tools use lagging indicators (detect delay after it happens)
- Opens a research question: does sentiment predict delay better than velocity alone?

### Technology Stack
- `transformers` (HuggingFace) — DistilBERT sentiment model
- `datasets` — for fine-tuning on developer corpus
- SQLite `sentiment_log` table (new schema)
- Rolling average computation in FastAPI background task

---

## Novelty 10 — Counterfactual "What-If" Schedule Simulation Engine

### Category
Causal Inference / Simulation

### The Problem It Solves
Your SQLite version history (Novelty 5) records every schedule adaptation — but only for reporting. A supervisor can see *that* the schedule drifted, but cannot ask *why* or *what would have happened differently*. The historical record is passive.

### The Novelty
You introduce a **Monte Carlo counterfactual simulation engine** that uses the version history as a causal baseline. Supervisors can pose interventional questions:

- "What would have happened if we added one developer in Week 3?"
- "What if the backend module had finished on time?"
- "What if we had used 12-week sprints instead of 8-week sprints?"

The system generates a probabilistic alternate timeline against the real one — a genuine causal reasoning capability.

### How It Works — Step by Step

1. **Parse the SQLite version history:** Load all schedule versions for a project from the `schedule_versions` table. Each version is a snapshot: planned dates, actual dates, team capacity, tasks completed.

2. **Build the causal model:** Represent the project as a Directed Acyclic Graph (DAG) where nodes are task completions and edges are dependencies. Edge weights come from observed delay propagation in the history.

3. **Define the intervention:** The supervisor inputs a counterfactual parameter via the dashboard — e.g., "team_size += 1 at week 3". The engine modifies the DAG at that node.

4. **Run Monte Carlo simulation:** Simulate 1,000 alternate project runs from the intervention point forward, sampling from historical delay distributions per task type. Collect the distribution of final completion dates.

5. **Compare timelines:** Display the real timeline (solid line) against the counterfactual distribution (shaded band) on a Gantt-style chart. Show the probability that the intervention would have resulted in on-time delivery.

### Connection to Existing System
Directly powered by Novelty 5 (SQLite schedule drift analytics). No new data collection is needed — the version history is the input. A new `/api/simulate` endpoint exposes the engine. The frontend adds a "What-if simulator" panel to the dashboard.

### Research Significance
- Transforms passive drift logging into active causal analysis
- Counterfactual reasoning is an open research area in project management — this is the first application to student academic projects
- Provides supervisors with evidence-based intervention guidance, not just hindsight reporting

### Technology Stack
- `pgmpy` or `dowhy` — causal DAG modeling
- `numpy` — Monte Carlo sampling
- New FastAPI endpoint: `POST /api/simulate`
- Gantt-style chart with confidence band (frontend, D3.js or Chart.js)

---

## Novelty 11 — Cross-Project Dependency Knowledge Graph

### Category
Knowledge Representation / Graph Databases

### The Problem It Solves
Every project in your system is treated as an isolated silo. In a real academic department, projects are interconnected: Project A's API module may be used by Project B's integration tests; Project C's shared library is a dependency of Projects D and E. When Project A delays, Projects B, C, D, and E are all at risk — but no tool currently propagates this signal.

### The Novelty
You build a **departmental knowledge graph** where WBS tasks across all projects are nodes and inter-project dependencies are edges. When the risk engine flags a task in Project A, the knowledge graph automatically propagates a risk signal to all downstream dependent tasks in other projects — across team boundaries.

### How It Works — Step by Step

1. **Extract inter-project dependencies:** Supervisors declare cross-project dependencies at project creation time (e.g., "Project B, Task: Integration Testing depends on Project A, Task: API Gateway completion"). These are stored as edges in the graph.

2. **Build the knowledge graph:** Use `NetworkX` (Python) or `Neo4j` (graph database) to represent all tasks across all active projects as nodes. Edges encode: same-project task ordering, cross-project dependencies, and shared team member relationships.

3. **Risk propagation algorithm:** When your Logistic Regression flags a task as HIGH RISK, a graph traversal (BFS/DFS) walks all downstream edges. Each downstream task receives a propagated risk increment based on its distance and dependency weight.

4. **Cross-project dashboard:** A new department-level dashboard (accessible only to supervisors) shows all active projects as interconnected nodes. Risk propagation is visualized as a heat map overlay on the graph.

5. **Automatic alert generation:** If propagated risk pushes a downstream task above the HIGH RISK threshold, that task's project team receives an automatic early warning — even though their own work is currently on schedule.

### Connection to Existing System
Consumes task data from the existing WBS extraction pipeline (Novelty 1) and risk scores from Novelty 3. The knowledge graph is a new layer — it does not replace any existing module. The SQLite database is extended with a `cross_project_edges` table, or optionally replaced with a Neo4j instance for larger deployments.

### Research Significance
- First academic PM tool to model inter-project risk propagation
- Reframes academic project management from isolated team scheduling to a departmental dependency network
- Enables a new research question: how much delay propagation occurs silently across student projects in a department?

### Technology Stack
- `networkx` — Python graph library (lightweight option)
- `neo4j` with `py2neo` — full graph database (scalable option)
- BFS/DFS risk propagation algorithm
- Department-level graph visualization (D3.js force-directed graph, frontend)
- SQLite extension: `cross_project_edges` table

---

## Summary Comparison

| Novelty | Extends | Effort to Implement | Academic Impact |
|---|---|---|---|
| 6 — Federated learning | Novelty 2 (XGBoost) | High | Very High — privacy + ML |
| 7 — SHAP explainability | Novelty 3 (Logistic Reg.) | Low | High — XAI in scheduling |
| 8 — Pareto scheduling | BEDF scheduler | Medium | High — optimization theory |
| 9 — Sentiment signals | Novelty 4 (GitHub webhook) | Medium | High — affective computing |
| 10 — Counterfactual sim. | Novelty 5 (SQLite history) | Medium | Very High — causal inference |
| 11 — Knowledge graph | Novelty 1 + 3 | High | Very High — new research area |

### Recommended Priority for Supervisor Meeting

If your supervisor asks you to pick two additions to implement:

1. **Novelty 7 (SHAP)** — lowest implementation effort, highest immediate visibility. One import, one new API field, one new dashboard component. You can demonstrate it in a week.

2. **Novelty 10 (Counterfactual simulation)** — directly activates the SQLite version history that Novelty 5 collects but does not currently use analytically. It closes the most obvious gap in your existing design and introduces genuine causal reasoning.

---

*Document prepared as an extension proposal for the Integrated Project Management System (IPMS) research project.*
