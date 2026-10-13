# Common Integrated Solution Report – Component Content Collection Prompt

## Instructions for the Team Member

Please use this prompt in **your own ChatGPT conversation where your latest project files, thesis, research paper, implementation notes, screenshots, API documentation, and testing evidence are available**.

Attach or make sure ChatGPT can access the most up-to-date versions of your materials before using this prompt.

Then paste **everything below the line** into your chat.

---

# PROMPT TO PASTE INTO CHATGPT

I am preparing the **Common Integrated Solution Report** for our Final Year Research project:

**Project:** Intelligent Project Management System for Undergraduate Students  
**Group ID:** R26-IT-095

The common report must present the project as **one integrated system**, not as four separate individual theses.

I need you to extract and prepare a **Component Handoff Pack** for my individual component using the files and information available in this chat.

## Critical Instructions

1. Use my **latest available thesis, research paper, implementation/code documentation, API documentation, screenshots, test results, evaluation results, and other project files** as the primary sources.
2. If there are multiple versions of the same document, prefer the **latest/final version**.
3. Do **not invent, assume, or estimate** missing facts.
4. If something is not supported by my files, write: **“Not confirmed from the available project evidence.”**
5. Do not exaggerate research claims.
6. Clearly distinguish:
   - real data vs synthetic data;
   - research results vs implementation/testing results;
   - implemented functionality vs proposed/future functionality.
7. Preserve exact endpoint names, metric values, dataset sizes, algorithms, models, technologies, and component names wherever they are available.
8. Keep the content concise but sufficiently detailed for another group member to write the common report.
9. Do not write a full thesis chapter. Produce the structured handoff pack requested below.
10. Where possible, mention the **source file/section/page** from which important facts were obtained so the group can verify them later.

---

# REQUIRED OUTPUT

## 1. Component Identity

**Student Name:**  
**Student ID:**  
**Official Component Title:**  
**Short Component Name:**  

### One-Sentence Component Purpose
Write one sentence explaining what this component does within the complete IPMS.

---

## 2. Subproblem Addressed

### 2.1 Specific Subproblem
Explain the exact problem this component solves in **3–6 sentences**.

### 2.2 Why This Subproblem Matters
Explain why the complete IPMS requires this component.

### 2.3 Research Gap
Summarize the specific research/technical gap addressed by this component in **3–5 sentences**.

### 2.4 Scope
State what is inside and outside the component scope.

---

## 3. Stakeholders and User Needs

List the stakeholders directly relevant to this component.

| Stakeholder | Need / Problem | How the Component Helps |
|---|---|---|

Also identify the **primary user** of the component.

---

## 4. Inputs, Processing and Outputs

### 4.1 Main Inputs

| Input | Source | Format / Structure | Purpose |
|---|---|---|---|

### 4.2 Core Processing / Method

Explain the main computational/research method in a concise form.

Include only methods that are actually implemented or evaluated.

| Method / Model | Purpose | Important Configuration | Output |
|---|---|---|---|

### 4.3 Main Outputs

| Output | Used By | Purpose |
|---|---|---|

---

## 5. Contribution to the Complete IPMS

Explain how this component contributes to the overall system.

Include:
- what stage of the project lifecycle it supports;
- what information it creates;
- what downstream components depend on it;
- what upstream components or shared services it depends on;
- what would be missing from the IPMS if this component did not exist.

Keep this section focused on **integration value**, not individual research novelty.

---

## 6. Technology Stack

Provide only technologies actually used in the implementation.

| Layer / Purpose | Technology | How It Is Used |
|---|---|---|
| Frontend | | |
| Backend | | |
| Database | | |
| AI / ML / Optimization | | |
| File Processing | | |
| APIs / Integration | | |
| Deployment / Runtime | | |
| Other Important Libraries | | |

If a category is not applicable, write **N/A**.

---

## 7. Architecture Summary

### 7.1 Component Architecture
Describe the internal architecture in **one short paragraph**.

### 7.2 Main Modules / Services

| Module / Service | Responsibility |
|---|---|

Use actual module/service names when known.

### 7.3 Suggested Architecture Diagram Content
Provide a simple diagram flow that can later be redrawn for the common report.

Example format:

`User → Frontend → Backend API → Core Service → Database → Integration API`

Use the actual architecture of this component.

---

## 8. Integration with the Other Components

**This is one of the most important sections.**

### 8.1 Data Received from Other Components

| Source Component | Data Received | API / Mechanism | Shared Identifier(s) |
|---|---|---|---|

If none, explicitly state that the component can start independently.

### 8.2 Data Provided to Other Components

| Destination Component | Data Provided | API / Mechanism | Shared Identifier(s) |
|---|---|---|---|

### 8.3 Important API Endpoints

List the integration-relevant endpoints only.

| Method | Endpoint | Purpose | Main Request Data | Main Response Data |
|---|---|---|---|---|

### 8.4 Shared Data Models / Identifiers

List identifiers or objects used across components, for example:
- Student ID
- Team ID
- Project ID
- Supervisor ID
- Allocation ID
- Task ID
- Proposal ID

Only include identifiers confirmed in the project.

### 8.5 Integration Sequence

Write the actual integration sequence in order.

### 8.6 Integration Failure / Exception Handling

State any implemented or documented behavior for:
- missing upstream data;
- invalid IDs;
- unavailable APIs;
- validation failures;
- stale data;
- fallback behavior.

If not documented, say so.

---

## 9. End-to-End Role in the Complete System

Explain in **5–10 sentences** where this component fits in the full IPMS workflow.

Focus on the actual relationship between:

`Team Formation → Planning/Scheduling → Proposal Analysis → Risk/Contribution Monitoring`

Adjust the sequence according to implementation evidence.

---

## 10. Research Method Summary

Do **not** reproduce the full methodology chapter.

### 10.1 Research Design
2–4 sentences.

### 10.2 Data / Datasets / Participants
State:
- dataset size;
- real or synthetic;
- train/test split if relevant;
- number of participants if relevant;
- number of experiments/runs if relevant.

### 10.3 Main Evaluation Metrics
List the metrics actually used.

### 10.4 Baselines / Comparators
List only the actual comparators.

---

## 11. Strongest Research Results

Provide the **5–8 most important quantitative research results**.

| Result | Value | What It Demonstrates | Data Type (Real/Synthetic/Controlled) |
|---|---:|---|---|

Important:
- preserve exact numbers;
- do not combine results from different experiments incorrectly;
- clearly label synthetic results;
- do not turn a technical metric into an unsupported claim.

Then provide a **3–5 sentence interpretation** suitable for a common report.

---

## 12. Product and Technical Results

Provide the strongest implementation-level evidence.

| Technical Result / Test | Outcome | Evidence |
|---|---|---|

Examples may include successful integration, API behavior, build/test status, runtime, scalability, structural validation, error handling, deployment, and database lifecycle.

---

## 13. Stakeholder / User Validation

Provide only validation that actually occurred.

State:
- who evaluated or reviewed it;
- what was reviewed;
- how feedback was collected;
- what was changed or confirmed;
- whether a formal usability study was conducted.

If no formal usability/user study exists, state that clearly.

---

## 14. Limitations and Threats

Provide the **4–8 most important limitations** relevant to the common report.

### Research Limitations
- ...

### Product / Technical Limitations
- ...

### Integration Limitations
- ...

---

## 15. Commercialisation and Sustainability Input

The common report contains a Commercialisation, Sustainability and Responsible Innovation chapter.

### 15.1 Value Proposition
What practical value does this component add to the complete IPMS?

### 15.2 Target Beneficiaries
Who benefits?

### 15.3 Adoption Considerations
What would an institution need to adopt this component?

### 15.4 Costs / Resources
What infrastructure, software, staff, data, or maintenance resources are required?

### 15.5 Intellectual Property / Licensing
State anything documented about ownership, open-source libraries, model licences, third-party APIs, or data restrictions. If not confirmed, state so.

### 15.6 Privacy / Ethics / Responsible AI
Summarize the important issues and safeguards.

### 15.7 Sustainability
Explain how the component could remain maintainable and useful after the research project.

### 15.8 Relevant Sustainable Development Goals
Only include SDGs that can be reasonably justified from project evidence. Do not exaggerate impact.

---

## 16. Individual and Shared Team Contribution

### 16.1 Individual Research Contribution
3–6 bullets.

### 16.2 Individual Development Contribution
3–6 bullets.

### 16.3 Integration Contribution
State what this member personally implemented or supported for cross-component integration.

### 16.4 Shared Group Work
List only confirmed shared tasks such as overall architecture, UI consistency, API integration, deployment, documentation, presentation, or testing.

Do not assign work to people without evidence.

---

## 17. Suggested Content for the Common Report

Based on my component, provide short, paste-ready content for these common-report locations:

### Chapter 2 – Subproblem Summary
Maximum 150 words.

### Chapter 3 – Component Summary
Maximum 180 words.

It must cover:
- owner;
- subproblem;
- input;
- method;
- output;
- role in IPMS.

### Chapter 4 – Integration Summary
Maximum 180 words.

### Chapter 5 – Implementation Summary
Maximum 120 words.

### Chapter 6 – Results Summary
Maximum 180 words.

### Chapter 7 – Commercialisation / Sustainability Contribution
Maximum 120 words.

### Chapter 8 – Future Direction Relevant to This Component
Maximum 80 words.

Do not repeat the same wording across sections.

---

## 18. Figures, Tables and Screenshots Available

| Visual | What It Shows | Suggested Use in Common Report | Source |
|---|---|---|---|

Recommend only the strongest visuals.

---

## 19. References Relevant to the Common Report

List only the references from my individual work that are likely to be useful in the **common integrated report**.

| Ref. | Reference | Common-Report Relevance |
|---|---|---|

Use IEEE format where possible. Do not dump the entire individual-thesis bibliography unless all sources are genuinely needed.

---

## 20. Evidence / Verification Checklist

| Claim / Information | Confirmed? | Source File / Section / Page | Notes |
|---|---|---|---|

Include the most important:
- component title;
- core method;
- technology stack;
- integration endpoints;
- datasets;
- main results;
- testing evidence;
- stakeholder validation;
- limitations.

---

# FINAL RESPONSE FORMAT

Return the completed handoff as Markdown with this title:

# Common Report Component Handoff Pack

At the very top include:

**Component Owner:**  
**Student ID:**  
**Component:**  
**Prepared From:** [list the main files used]

At the end include:

## Missing / Unconfirmed Information

List anything needed for the common report that could not be confirmed from the available files.

## Files the Group Should Request From Me

List any source files, screenshots, API docs, diagrams, test evidence, or other artefacts that the group coordinator should ask me to send separately.

---

**Do not ask me to manually rewrite information that already exists in my uploaded files. Search/read the available files first and extract it yourself.**
