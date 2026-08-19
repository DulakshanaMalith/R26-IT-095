# Intelligent Team Formation and Topic Feasibility Analysis

## Intelligent Project Management System for Undergraduate Students

This repository contains the **Intelligent Team Formation and Topic Feasibility Analysis** component of an Intelligent Project Management System designed for undergraduate project environments.

The component provides academic staff with decision support for:

1. validating cohort and project data,
2. generating alternative project-team allocations,
3. comparing trade-offs between technical requirement satisfaction and student project preferences, and
4. analyzing the technical feasibility of assigning an existing team to a selected project topic.

The final system uses a **Heuristic-Seeded NSGA-II multi-objective optimization approach** for team formation and a deterministic requirement-coverage model for topic technical feasibility.

---

# 1. Research Motivation

Undergraduate project teams must often be formed while considering multiple competing factors.

A technically strong allocation may not align well with students' preferred projects, while an allocation that maximizes student preferences may result in inadequate technical competency for some project requirements.

Many team-formation approaches combine multiple criteria into a single weighted score.

This system instead preserves two important objectives separately:

- **Technical Requirement Deficit**
- **Student Project Preference Dissatisfaction**

The optimizer therefore produces a set of nondominated alternatives rather than automatically selecting a single "best" allocation.

Academic staff can inspect these alternatives and select an allocation based on the trade-off considered appropriate for the cohort.

---

# 2. Final System Scope

The final implemented component contains two main workflows.

## 2.1 Intelligent Team Formation

The system receives:

- student technology competency levels,
- student project preferences,
- approved projects,
- project team sizes,
- project technology requirements,
- technology competency thresholds,
- required number of competent members.

The system then applies **Heuristic-Seeded NSGA-II V3** to discover Pareto-optimal team allocation alternatives.

Each alternative exposes:

- technical requirement coverage,
- technical requirement deficit,
- student preference satisfaction,
- student preference dissatisfaction,
- project-level technical coverage,
- unmet technical requirements,
- assigned students,
- student preference ranks,
- relevant student competency levels.

The system does not automatically choose one Pareto solution.

The alternatives are presented to academic staff as decision support.

---

## 2.2 Topic Technical Feasibility

Topic feasibility is implemented as a separate deterministic stage.

It evaluates:

> Can this existing team satisfy the modeled technical requirements of this selected project/topic?

The analysis checks each required technology using:

- minimum competency level,
- required number of competent students,
- number of currently qualified students.

The output includes:

- overall technical coverage,
- technical deficit,
- covered requirements,
- identified technical gaps,
- qualified students,
- competency evidence for each team member.

This module evaluates **technical requirement coverage only**.

It does **not** predict:

- project grades,
- project completion,
- teamwork quality,
- student performance,
- or overall project success.

---

# 3. Research Questions

The component is based on the following research questions.

### RQ1

How can technology-specific student competencies and project requirements be represented to provide an interpretable measure of technical requirement coverage?

### RQ2

How does Pareto-based multi-objective optimization represent trade-offs between technical requirement satisfaction and student project preference under different levels of objective conflict?

### RQ3

How does heuristic-seeded NSGA-II compare with greedy, random, weighted single-objective, and unseeded NSGA-II approaches in Pareto-front quality, objective endpoints, scalability, and computational cost?

---

# 4. Mathematical Formulation

## 4.1 Student Competency

Each student's self-reported technology competency is represented using a five-level scale:

| Level | Interpretation |
|---|---|
| 1 | Little or no practical experience |
| 2 | Can perform basic tasks with guidance |
| 3 | Can independently implement normal features |
| 4 | Strong practical ability and troubleshooting capability |
| 5 | Advanced practical ability and ability to lead technical work |

The system treats these ratings as **ordinal self-reported competency data**.

---

# 5. Objective 1 — Technical Requirement Deficit

Let:

- `x_ik` = competency of student `i` in technology `k`
- `L_pk` = minimum competency level required for project `p`
- `M_pk` = number of competent members required

A student qualifies for a requirement when:

```text
x_ik >= L_pk