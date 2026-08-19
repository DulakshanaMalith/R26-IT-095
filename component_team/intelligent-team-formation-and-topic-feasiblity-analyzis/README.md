Intelligent Team Formation and Topic Feasibility Analysis

Intelligent Project Management System for Undergraduate Students

This repository contains the Intelligent Team Formation and Topic Feasibility Analysis component of an Intelligent Project Management System designed for undergraduate project environments.

The component provides academic staff with decision support for:

validating cohort and project data,

generating alternative project-team allocations,

comparing trade-offs between technical requirement satisfaction and student project preferences, and

analyzing the technical feasibility of assigning an existing team to a selected project/topic.

The final system uses a Heuristic-Seeded NSGA-II V3 multi-objective optimization approach for team formation and a deterministic requirement-coverage model for topic technical feasibility.

1. Research Motivation

Undergraduate project teams often need to be formed while considering multiple competing factors.

A technically strong allocation may not align well with students' preferred projects, while an allocation that maximizes student preferences may result in inadequate technical competency for some project requirements.

Many team-formation approaches combine multiple criteria into a single weighted score.

This system instead preserves two important objectives separately:

Technical Requirement Deficit

Student Project Preference Dissatisfaction

The optimizer therefore produces a set of nondominated alternatives rather than automatically selecting a single "best" allocation.

Academic staff can inspect these alternatives and select an allocation based on the trade-off considered appropriate for the cohort.

2. Final System Scope

The final implemented component contains two main workflows.

2.1 Intelligent Team Formation

The system receives:

student technology competency levels,

student project preferences,

approved projects,

project team sizes,

project technology requirements,

technology competency thresholds,

required number of competent members.

The system then applies Heuristic-Seeded NSGA-II V3 to discover Pareto-optimal team allocation alternatives.

Each alternative exposes:

technical requirement coverage,

technical requirement deficit,

student preference satisfaction,

student preference dissatisfaction,

project-level technical coverage,

unmet technical requirements,

assigned students,

student preference ranks,

relevant student competency levels.

The system does not automatically choose one Pareto solution.

The alternatives are presented to academic staff as decision support.

2.2 Topic Technical Feasibility

Topic feasibility is implemented as a separate deterministic stage.

It evaluates:

Can this existing team satisfy the modeled technical requirements of this selected project/topic?

The analysis checks each required technology using:

minimum competency level,

required number of competent students,

number of currently qualified students.

The output includes:

overall technical coverage,

technical deficit,

covered requirements,

identified technical gaps,

qualified students,

competency evidence for each team member.

This module evaluates technical requirement coverage only.

It does not predict:

project grades,

project completion,

teamwork quality,

student performance,

or overall project success.

3. Research Questions

The component is based on the following research questions.

RQ1

How can technology-specific student competencies and project requirements be represented to provide an interpretable measure of technical requirement coverage?

RQ2

How does Pareto-based multi-objective optimization represent trade-offs between technical requirement satisfaction and student project preference under different levels of objective conflict?

RQ3

How does heuristic-seeded NSGA-II compare with greedy, random, weighted single-objective, and unseeded NSGA-II approaches in Pareto-front quality, objective endpoints, scalability, and computational cost?

4. Student Competency Representation

Each student's self-reported technology competency is represented using a five-level scale:

Level

Interpretation

1

Little or no practical experience

2

Can perform basic tasks with guidance

3

Can independently implement normal features

4

Strong practical ability and can troubleshoot complex features

5

Advanced practical ability and can lead technical work

The system treats these ratings as ordinal self-reported competency data.

The active technology catalog contains:

React

HTML/CSS

Angular

Vue

NodeJS

Express

Java

PHP

FastAPI

MongoDB

MySQL

PostgreSQL

Firebase

Python

TensorFlow

Pandas

5. Objective 1 — Technical Requirement Deficit

Let:

x_ik = competency of student i in technology k

L_pk = minimum competency level required for project p

M_pk = number of competent members required for project p and technology k

A student qualifies for a requirement when:

x_ik >= L_pk

Define:

q_ipk = 1, if x_ik >= L_pk
q_ipk = 0, otherwise

The number of qualified students assigned to project p for requirement k is:

N_pk = sum(q_ipk) for students assigned to project p

Requirement coverage is:

C_pk = min(1, N_pk / M_pk)

Project technical coverage is:

C_p = (1 / |R_p|) * sum(C_pk)

where R_p is the set of technical requirements for project p.

Project technical deficit is:

D_p = 1 - C_p

The first optimization objective is:

f1 = (1 / P) * sum(D_p)

The optimizer minimizes:

f1

Lower technical deficit is better.

A value of:

0

means that all modeled technical requirements are fully covered.

The system uses a threshold-based qualification model instead of treating ordinal self-reported competency levels as exact linear quantities.

6. Objective 2 — Preference Dissatisfaction

Each student ranks project preferences.

When all P projects are ranked, preference dissatisfaction is normalized as:

d_ip = (r_ip - 1) / (P - 1)

where r_ip is the rank assigned by student i to project p.

Therefore:

First preference -> 0
Last preference  -> 1

For partial Top-K preference lists:

Ranked project dissatisfaction = (rank - 1) / K
Unranked project dissatisfaction = 1

The second optimization objective is:

f2 = (1 / N) * sum(d_i,a(i))

where a(i) is the project assigned to student i.

The optimizer minimizes:

f2

Lower preference dissatisfaction is better.

7. Multi-Objective Optimization

The two objectives are deliberately kept separate:

F = (f1, f2)

The system does not combine the objectives using a fixed weighted score.

This allows NSGA-II to expose multiple nondominated alternatives representing different trade-offs between:

technical requirement satisfaction,

student project preference satisfaction.

8. Heuristic-Seeded NSGA-II V3

The final optimizer is:

Heuristic-Seeded NSGA-II V3

V3 retains the NSGA-II representation and evolutionary operators while improving initialization.

The initial population contains:

a technically oriented greedy allocation,

a preference-oriented greedy allocation,

local swap variants around the heuristic solutions,

randomly generated feasible allocations.

The heuristic solutions act only as initialization anchors.

The optimizer remains multi-objective and does not use a hidden weighted objective.

For large instances, the system refers to results as:

discovered nondominated solutions

or:

approximated Pareto fronts

because the true Pareto front is not exhaustively known.

9. Optimization Constraints

The team-formation optimizer enforces:

Each student is assigned exactly once.

Each approved project receives its required team size.

Only valid approved projects participate in allocation.

The total number of project team slots must equal the number of students being allocated.

10. Input Workbook

Academic staff provide cohort data using an Excel .xlsx workbook.

The workbook contains the following sheets.

10.1 Students

Contains:

StudentID
React
HTML_CSS
Angular
Vue
NodeJS
Express
Java
PHP
FastAPI
MongoDB
MySQL
PostgreSQL
Firebase
Python
TensorFlow
Pandas

Competencies are recorded from 1 to 5.

10.2 Preferences

Contains student project preferences.

Example:

StudentID
Preference1
Preference2
Preference3

10.3 Projects

Contains:

ProjectID
ProjectTitle
TeamSize
Status

10.4 ProjectRequirements

Contains:

ProjectID
Technology
MinLevel
RequiredMembers

Example:

P02
Python
3
2

means that project P02 requires at least two team members with Python competency level 3 or above.

10.5 Domains

Contains the controlled project/supervisor domain vocabulary.

10.6 ProjectDomains

Maps projects to their relevant domains.

10.7 Supervisors

Contains supervisor information such as:

SupervisorID
SupervisorName
MaximumTeams
CurrentLoad

Supervisor information is validated as part of the workbook structure.

Supervisor assignment is a separate downstream concern and is not part of the active NSGA-II team-formation objective set.

10.8 SupervisorDomains

Contains supervisor domain mappings using:

SupervisorID
Type
Domain

where Type is either:

Expertise
Interest

11. Workbook Validation

The system performs validation before optimization.

Examples of detected errors include:

duplicate student IDs,

missing competency ratings,

competency values outside the 1–5 range,

unknown technologies,

invalid requirement levels,

duplicate project requirements,

invalid required-member counts,

unknown student references,

unknown project references,

duplicate preferences,

unknown domains,

invalid supervisor loads,

missing supervisor expertise,

insufficient supervisor capacity,

cohort/team-slot mismatches.

Validation issues are classified as:

ERROR
WARNING

An ERROR blocks team formation.

A WARNING is reported to academic staff but does not necessarily block processing.

Invalid workbooks cannot reach the optimizer.

12. Staff Decision-Support Interface

The React frontend provides:

workbook upload,

workbook validation,

optimization execution,

Pareto scatter plot,

Pareto solution cards,

technical coverage metrics,

preference satisfaction metrics,

project-level requirement analysis,

student allocation details,

student preference evidence,

student competency evidence,

topic technical feasibility analysis,

technical-gap reporting,

team-size mismatch warnings.

The Pareto chart uses:

X-axis: Technical Requirement Deficit
Y-axis: Preference Dissatisfaction

Lower values on both axes are preferable.

The interface presents alternatives rather than automatically selecting a mandatory solution.

13. Topic Technical Feasibility Calculation

For an existing team and selected project, the system evaluates each technical requirement.

Example:

Technology: Python
Minimum Level: 3
Required Members: 2
Qualified Members: 1

Coverage is:

1 / 2 = 0.5

and the requirement is marked:

Gap

If qualified members meet or exceed the requirement:

Coverage = 1.0
Status = Covered

Overall topic technical coverage is the average of the individual requirement coverage values.

Technical deficit is:

1 - Technical Coverage

The analysis provides deterministic technical evidence and does not predict project success.

14. Team Size and Technical Feasibility

Topic feasibility can still be calculated for an incomplete or temporary team.

For example:

Expected Team Size: 4
Actual Team Size: 3

The system reports:

team_size_matches_project = false

while still calculating technical requirement coverage.

This distinction is intentional.

A team can technically cover all modeled technology requirements while still failing the project's administrative team-size requirement.

The frontend displays a warning when this condition occurs.

15. Technology Stack

Backend

Python
FastAPI
Pydantic
OpenPyXL
DEAP
Uvicorn
python-multipart

Frontend

React
Vite
Axios
Recharts
Tailwind CSS

Data Input

Microsoft Excel (.xlsx)

16. Repository Structure

intelligent-team-formation-and-topic-feasiblity-analyzis/
│
├── backend-fastapi/
│   │
│   ├── app/
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── cohort_import.py
│   │   │
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── cohort_routes.py
│   │   │   └── topic_feasibility_routes.py
│   │   │
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── baseline_team_formation.py
│   │       ├── cohort_data_service.py
│   │       ├── evaluation_experiment_runner.py
│   │       ├── evaluation_metrics.py
│   │       ├── exact_search_verifier.py
│   │       ├── excel_parser.py
│   │       ├── nsga2_optimizer.py
│   │       ├── nsga2_verification_service.py
│   │       ├── scalability_experiment_service.py
│   │       ├── stochastic_baselines.py
│   │       ├── synthetic_cohort_generator.py
│   │       ├── team_formation_objectives.py
│   │       ├── team_formation_response_service.py
│   │       ├── topic_feasibility_service.py
│   │       ├── validation_service.py
│   │       └── workbook_validation_service.py
│   │
│   ├── legacy/
│   │   └── prototype/
│   │
│   ├── test_data/
│   ├── test_results/
│   ├── main.py
│   └── requirements.txt
│
├── frontend/
│   │
│   ├── public/
│   │
│   ├── src/
│   │   ├── components/
│   │   │   ├── StaffTeamFormation.jsx
│   │   │   └── TopicFeasibilityPanel.jsx
│   │   │
│   │   ├── legacy/
│   │   ├── App.jsx
│   │   ├── index.css
│   │   └── main.jsx
│   │
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.js
│   └── eslint.config.js
│
├── .gitignore
└── README.md

17. Backend Installation

Open a terminal inside:

backend-fastapi

Create a virtual environment if desired:

python -m venv venv

Windows activation:

venv\Scripts\activate

Install dependencies:

pip install -r requirements.txt

Start the backend:

uvicorn main:app --reload --port 8003

The API runs at:

http://127.0.0.1:8003

Swagger documentation:

http://127.0.0.1:8003/docs

Health check:

http://127.0.0.1:8003/health

Expected response:

{
  "status": "healthy"
}

18. Frontend Installation

Open another terminal inside:

frontend

Install dependencies:

npm install

Start the development server:

npm run dev

Open the URL shown by Vite in the terminal.

Depending on local configuration, the frontend may run on a port such as:

http://127.0.0.1:3001

or:

http://127.0.0.1:5173

The backend CORS configuration must allow the frontend origin being used.

19. Production Build and Code Checks

Frontend lint:

npm run lint

Frontend production build:

npm run build

Backend compile check:

python -m compileall app

The final cleaned implementation has been verified with successful linting, production build, and backend compilation.

20. API Endpoints

20.1 Root

GET /

Returns basic API metadata and active workflow information.

20.2 Health Check

GET /health

20.3 Validate Workbook

POST /api/cohort/validate

Input:

multipart/form-data
file = .xlsx workbook

Returns:

validation status,

summary counts,

structured errors,

warnings.

20.4 Run Team Formation

POST /api/cohort/optimize

Input:

multipart/form-data
file = validated .xlsx workbook

Returns:

optimizer metadata,

discovered Pareto alternatives,

objective values,

project teams,

requirement coverage,

assigned students,

preference evidence,

competency evidence.

20.5 Analyze Topic Technical Feasibility

POST /api/topic-feasibility/analyze

Input:

file
project_id
team_student_ids

Example:

project_id = P02

team_student_ids =
SIM-001,SIM-002,SIM-008,SIM-012

Returns:

technical coverage,

technical deficit,

team-size status,

covered requirements,

technical gaps,

qualified students,

individual competency evidence.

21. Evaluation Methodology

The V3 optimizer was evaluated against:

Technical Greedy

Preference Greedy

Random Search

Weighted Single-Objective GA

Unseeded NSGA-II

Heuristic-Seeded NSGA-II V3

Synthetic cohorts were generated at:

20 students
40 students
60 students
100 students

under:

Low preference conflict
Medium preference conflict
High preference conflict

The final experiment used:

10 dataset seeds
3 optimizer seeds
population size = 120
generations = 150

Random Search and Weighted Single-Objective GA were allocated comparable evaluation budgets.

The principal multi-objective metric was hypervolume, where higher values indicate better coverage of the objective space relative to the selected reference point.

Runtime, objective endpoints, and discovered nondominated solution counts were also measured.

22. Exact Verification

Small 12-student scenarios were evaluated using exhaustive search.

For:

12 students
3 projects
4 students per team

there are:

34,650

distinct feasible allocations.

These instances were used to compare NSGA-II results against the true Pareto front.

The Medium-conflict exact Pareto objective points were:

(0, 0.208333333333)
(0.055555555556, 0.125)
(0.222222222222, 0.083333333333)

The High-conflict exact Pareto objective points were:

(0, 0.375)
(0.055555555556, 0.291666666667)
(0.222222222222, 0.208333333333)
(0.388888888889, 0.166666666667)

V3 recovered the complete exact Pareto front in all final repeated Medium- and High-conflict verification runs.

23. Final Experimental Design

The final large-scale evaluation used:

4 cohort sizes
×
3 conflict levels
×
10 dataset seeds
=
120 synthetic datasets

Multiple optimizer seeds were used for stochastic methods.

The final evaluation produced:

1,680 experiment records

across all compared methods.

24. Key Evaluation Findings

Across the final evaluation, Heuristic-Seeded NSGA-II V3 achieved the strongest overall hypervolume performance among the compared approaches.

Overall mean hypervolume:

V3                          0.947855
Preference Greedy           0.779318
Unseeded NSGA-II            0.653219
Weighted Single-Objective   0.602382
Technical Greedy            0.372059
Random Search               0.363178

V3 mean hypervolume by cohort size:

20 students   0.984609
40 students   0.961982
60 students   0.938313
100 students  0.906516

V3 mean runtime by cohort size was approximately:

20 students    2.20 s
40 students    4.39 s
60 students    6.68 s
100 students  13.33 s

V3 mean hypervolume by conflict level:

Low     1.0201
Medium  0.957639
High    0.865827

Mean discovered front size for V3:

Low conflict      1.00
Medium conflict  13.21
High conflict    28.78

This illustrates that stronger conflict between technical and preference objectives produces a richer trade-off space.

25. Statistical Evaluation

Statistical testing was performed on dataset-level medians, where repeated optimizer runs were collapsed per dataset.

For the four stochastic methods:

Heuristic-Seeded NSGA-II V3

Unseeded NSGA-II

Weighted Single-Objective GA

Random Search

the Friedman test produced:

χ²(3) = 326.081266
p = 2.25 × 10^-70
Kendall's W = 0.90578

Mean ranks were:

V3                         1.1417
Unseeded NSGA-II           2.0375
Weighted Single-Objective  2.8208
Random Search              4.0000

One-sided paired Wilcoxon tests with Holm correction showed that V3 achieved significantly higher hypervolume than the three stochastic comparators overall:

V3 vs Random Search
adjusted p = 2.957928 × 10^-21

V3 vs Weighted Single-Objective
adjusted p = 2.957130 × 10^-20

V3 vs Unseeded NSGA-II
adjusted p = 7.832067 × 10^-20

All were below 0.001.

Some smaller 20-student per-condition comparisons were not significant after correction, indicating that the advantage of heuristic seeding becomes more pronounced as problem size increases.

26. Objective Endpoint Interpretation

The preference-oriented endpoint with:

f2 = 0

was discovered in all final V3 runs.

The best technical endpoint reached:

f1 = 0

in approximately:

78.06%

of final V3 runs.

The mean technical endpoint deficit was approximately:

0.003122685

which corresponds to approximately:

99.69%

technical coverage at the technical-oriented endpoint.

These endpoints should not be interpreted as the same allocation.

They represent different parts of the discovered trade-off frontier.

27. Important Interpretation Notes

The system should not be interpreted as an automatic decision maker.

It provides decision support to academic staff.

Student competencies are self-reported values.

Therefore, the system should not claim that those ratings are objective measurements of student ability.

The optimizer does not predict academic performance.

The topic feasibility module does not predict project success.

The Pareto optimizer presents alternative allocations rather than selecting one mandatory allocation.

Supervisor assignment is not a third NSGA-II objective.

28. Legacy Prototype

Earlier versions of this research explored:

XGBoost-based academic performance models,

SBERT-based semantic analysis,

demographic objectives,

academic preparedness objectives,

four-objective optimization.

These approaches are retained under:

legacy/

for development history only.

They are not part of the final V3 research workflow.

The final active implementation is based on:

technology competency
project technical requirements
project preferences
Pareto multi-objective team formation
deterministic technical feasibility

29. Testing

The final system has been integration-tested for:

valid workbook processing,

invalid workbook detection,

optimization blocking for invalid workbooks,

unknown project IDs,

duplicate student IDs,

unknown student IDs,

wrong team sizes,

technically covered teams,

teams containing technical gaps,

cross-topic feasibility analysis,

Pareto solution switching,

incorrect file types,

frontend/backend integration,

CORS configuration,

frontend linting,

production build,

backend compilation.

The intentionally invalid test workbook produces structured validation errors without crashing the application.

30. Demonstration Workflow

A recommended demonstration sequence is:

1. Start the backend.

2. Start the frontend.

3. Upload a valid cohort workbook.

4. Click Validate Workbook.

5. Show the validation summary.

6. Click Run Team Formation.

7. Explain the Pareto scatter plot.

8. Compare the technical-oriented,
   trade-off, and preference-oriented solutions.

9. Open project/team details.

10. Show requirement coverage and student evidence.

11. Select an existing team.

12. Select a topic/project.

13. Run Topic Technical Feasibility.

14. Demonstrate a fully covered topic.

15. Demonstrate another team/topic combination
    containing technical gaps.

31. Research Contribution

The contribution of this component is not the invention of NSGA-II itself.

The research contribution is the development and evaluation of a staff-oriented project-team formation decision-support approach in which:

technical project requirement deficit

and:

student project preference dissatisfaction

remain separate competing objectives.

This allows academic staff to inspect Pareto trade-offs instead of relying on a single weighted or ranked solution.

The system further provides interpretable technical requirement evidence and a separate deterministic topic technical-feasibility stage.

32. Current Final Workflow

Academic Staff
      |
      v
Cohort Excel Workbook
      |
      v
Workbook Validation
      |
      v
Validated Cohort Data
      |
      v
Heuristic-Seeded NSGA-II V3
      |
      v
Discovered Pareto Alternatives
      |
      v
Staff Decision
      |
      v
Selected Team / Project Allocation
      |
      v
Topic Technical Feasibility
      |
      v
Technical Coverage + Identified Gaps

33. Component Status

Current implementation status:

Workbook Validation                 COMPLETE
Team Formation Objectives           COMPLETE
Exact Search Verification           COMPLETE
NSGA-II V3                          COMPLETE
Heuristic Seeding                   COMPLETE
Synthetic Evaluation                COMPLETE
Baseline Comparison                 COMPLETE
Statistical Evaluation              COMPLETE
Staff Team-Formation API            COMPLETE
Staff Team-Formation Frontend       COMPLETE
Topic Feasibility Backend           COMPLETE
Topic Feasibility Frontend          COMPLETE
Integration Testing                 COMPLETE
Legacy Isolation                    COMPLETE
Repository Cleanup                  COMPLETE
Frontend Lint                       PASSED
Frontend Production Build           PASSED
Backend Compile Check               PASSED

34. Running the Final System

Backend

cd backend-fastapi
pip install -r requirements.txt
uvicorn main:app --reload --port 8003

Swagger:

http://127.0.0.1:8003/docs

Health:

http://127.0.0.1:8003/health

Frontend

cd frontend
npm install
npm run dev

Then open the local URL printed by Vite.

35. Reproducing the Frontend Quality Checks

cd frontend
npm run lint
npm run build

A Vite bundle-size warning may appear for the production bundle. This is a performance advisory and does not indicate a failed build.

36. Authors

This component was developed as part of an undergraduate final-year research project at the Sri Lanka Institute of Information Technology (SLIIT).

Component:

Intelligent Team Formation and Topic Feasibility Analysis

Parent System:

Intelligent Project Management System for Undergraduate Students

37. Academic Use

This repository was developed for academic research and educational purposes.

Any reuse of the research methodology, experimental results, software implementation, or documentation should provide