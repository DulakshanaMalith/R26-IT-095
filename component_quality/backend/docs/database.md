# Database and Persistence Documentation

## Summary

No SQL database is implemented. There is no ORM, schema migration framework, database connection pool, indexes, or foreign-key enforcement. Persistence is file-based:

- Runtime history: JSON files in `data/`
- Processed datasets: CSV files in `processed/`
- Model artifacts: pickle files in `models/`
- Generated reports: PDF files in `reports/`

The “database” documentation below describes the effective data stores that the application actually reads and writes.

## Runtime JSON Stores

| File | Written by | Read by | Purpose |
| --- | --- | --- | --- |
| `data/analysis_history.json` | `/analyze`, delete/clear helpers | history, dashboard, supervisor analytics, report generation | Successful proposal analysis records. |
| `data/grading_history.json` | `/grade-report`, clear helper | grading history, grading analytics, report generation | Semantic grading and readiness records. |
| `data/knowledge_graph_history.json` | `/knowledge-graph` | graph history, dashboard/history matching | Knowledge graph summaries. |
| `data/*.corrupted.json` | corruption recovery logic | not used by normal app flow | Backup of invalid JSON detected at runtime. |

## Runtime Store ER Diagram

This diagram shows logical relationships by shared IDs. They are not database-enforced foreign keys.

```mermaid
erDiagram
    ANALYSIS_HISTORY ||--o{ GRADING_HISTORY : "analysis_id"
    ANALYSIS_HISTORY ||--o{ KNOWLEDGE_GRAPH_HISTORY : "analysis_id"

    ANALYSIS_HISTORY {
        string id PK
        string analysis_id
        string request_id
        string timestamp
        string source
        string filename
        string student_name
        string student_id
        string proposal_title
        string input_text
        string predicted_tag
        string model_predicted_tag
        string classification_reason
        json retrieved_feedback
        json recommended_resources
    }

    GRADING_HISTORY {
        string id PK
        string analysis_id FK
        string timestamp
        string source
        string filename
        string input_text
        int word_count
        float predicted_score
        float percentage_score
        string label
        json section_scores
        json proposal_completeness
        json submission_readiness
        json final_proposal_assessment
        json final_readiness
        string model_status
        string warning
    }

    KNOWLEDGE_GRAPH_HISTORY {
        string timestamp
        string analysis_id FK
        string filename
        int concept_count
        json concepts
        json edges
        json missing_concepts
    }
```

## Processed Dataset Schemas

| File | Rows | Columns | Purpose |
| --- | ---: | --- | --- |
| `processed/exposia_annotations.csv` | 2,228 | `author`, `annotation_id`, `review`, `role`, `tag`, `annotated_text` | Base annotation corpus. |
| `processed/exposia_comments.csv` | 2,253 | `author`, `comment_id`, `annotation_id`, `review`, `role`, `comment_text`, `tags` | Reviewer comments linked to annotations. |
| `processed/exposia_grading_dataset.csv` | 165 | `author`, `submission_type`, `text`, `criteria_json`, `total_score` | Semantic grading model input/target rows. |
| `processed/exposia_reports.csv` | 55 | `author`, `topic`, `draft_text`, `final_text`, `draft_scores`, `final_scores` | Draft/final proposal corpus. |
| `processed/feedback_dataset.csv` | 2,152 | `annotated_text`, `tag`, `comment_text` | Initial retrieval dataset. |
| `processed/feedback_dataset_final.csv` | 2,134 | `annotated_text`, `tag`, `comment_text` | Final retrieval dataset. |
| `processed/weakness_dataset.csv` | 2,227 | `annotated_text`, `tag` | Initial classification dataset. |
| `processed/weakness_dataset_final.csv` | 2,035 | `annotated_text`, `tag` | Final production classification dataset. |
| `processed/weakness_dataset_labelclean_experimental.csv` | 1,913 | `annotated_text`, `tag` | Experimental label-cleaned classifier dataset. |

## Processed Dataset ER Diagram

```mermaid
erDiagram
    EXPOSIA_REPORTS ||--o{ EXPOSIA_ANNOTATIONS : author
    EXPOSIA_ANNOTATIONS ||--o{ EXPOSIA_COMMENTS : annotation_id
    EXPOSIA_REPORTS ||--o{ EXPOSIA_GRADING_DATASET : author
    EXPOSIA_ANNOTATIONS ||--o{ WEAKNESS_DATASET : annotated_text
    EXPOSIA_COMMENTS ||--o{ FEEDBACK_DATASET : comment_text

    EXPOSIA_REPORTS {
        string author
        string topic
        text draft_text
        text final_text
        json draft_scores
        json final_scores
    }
    EXPOSIA_ANNOTATIONS {
        string author
        string annotation_id
        string review
        string role
        string tag
        text annotated_text
    }
    EXPOSIA_COMMENTS {
        string author
        string comment_id
        string annotation_id
        string review
        string role
        text comment_text
        json tags
    }
    EXPOSIA_GRADING_DATASET {
        string author
        string submission_type
        text text
        json criteria_json
        float total_score
    }
```

## Keys, Relationships, and Constraints

| Concept | Implemented? | Notes |
| --- | --- | --- |
| Primary keys | Partially | Runtime history records have generated `id` fields; CSV datasets do not enforce uniqueness. |
| Foreign keys | Logical only | `analysis_id` links analysis, graph, and grading histories when supplied. |
| Indexes | No | Files are loaded and scanned in memory. |
| Constraints | Application-level | Validation is performed by Python/Pydantic and dataset scripts. |
| Migrations | No | Schema changes are handled by code-level normalization of legacy fields. |
| Normalization | Partial | Processed datasets separate reports, annotations, comments, and grading rows; runtime JSON records duplicate denormalized data for convenience. |

## Migration History

No formal migration history exists. The code contains compatibility helpers such as legacy field normalization for report payloads and grading/completeness payloads, and JSON corruption recovery that backs up invalid history files with `.corrupted.json`.

