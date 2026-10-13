# Project file cleanup — 2026-10-13

These 33 untracked/ignored local artifacts were removed from the project workspace after checking that no current app code or handoff document uses them. They were **moved, not permanently deleted**, to `D:\IPMS_cleanup_recovery_2026-10-13\`, with their relative paths preserved. They are not part of the Git push.

## Superseded documents and diagnostics (9)

1. `objects.txt` — old Git-object diagnostic dump.
2. `research_project_website.rar` — duplicate archive of the separately hosted website; the website folder itself remains local and is excluded from this repository.
3. `component_scheduling/IT22117014_Individual_Component_Dissertation.docx` — early draft.
4. `component_scheduling/IT22117014_Individual_Component_Dissertation_Expanded.docx` — superseded draft.
5. `component_scheduling/IT22117014_Individual_Component_Dissertation_Revised.docx` — superseded draft.
6. `component_scheduling/IT22117014_Individual_Component_Dissertation_Research_Corrected.docx` — superseded draft.
7. `component_scheduling/IT22117014_Individual_Thesis_SLIIT_Formatted_Draft_before_justification_2026-10-11.docx` — temporary pre-formatting backup; the original draft and corrected 12-point copy remain.
8. `component_scheduling/An_Evidence_Aware_Framework_for_Proposal_Driven_Project_Scheduling_and_Adaptive_Workload_Balancing__2_.pdf` — superseded paper render.
9. `component_scheduling/An_Evidence_Aware_Framework_for_Proposal_Driven_Project_Scheduling_and_Adaptive_Workload_Balancing__3_.pdf` — superseded paper render.

## Temporary PDF review images (24)

All of the following were page-rendering scratch files, not the linked handoff screenshots:

| Folder | Files moved |
| --- | --- |
| `component_scheduling/.paper_review_v4/` | `page1.png`, `page2.png`, `page3.png`, `page4.png`, `page5.png`, `page6.png` |
| `component_scheduling/.pdf_review_updated2/` | `page_1.png`, `page_2.png`, `page_3.png`, `page_4.png`, `page_5.png`, `page_6.png` |
| `component_scheduling/.pdf_review_updated3/` | `page_1.png`, `page_2.png`, `page_3.png`, `page_4.png`, `page_5.png`, `page_6.png` |
| `component_scheduling/paper_review_pages/` | `page_1.png`, `page_2.png`, `page_3.png`, `page_4.png`, `page_5.png`, `page_6.png` |

## Preserved intentionally

- `component_quality/training/data/raw/exposes/`: source proposal PDFs used by Quality training/evaluation scripts; ignored by Git.
- `component_scheduling/handoff_evidence/2026-10-10/`: screenshots explicitly linked from the component handoff pack.
- Current thesis candidate/formatted copies, official formatting templates, source proposal, cited research papers, and task-submission test fixtures; ignored by Git when they are PDF/DOCX files.
- Risk evaluation plots and frontend image assets that support documentation or UI.
- `research_project_website/`: local source for the separate website repository; never staged in this project repository.
- The nested Git-based commit fixture and legacy Team Formation prototype remain local but are excluded from this repository commit; they are not active runtime dependencies.
