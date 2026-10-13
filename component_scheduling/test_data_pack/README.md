# IPMS Scheduling and Progress-Tracking Test Data Pack

Generated synthetic data. It contains no real staff, student, participant, or research data.

## Contents

- `proposals/`: three distinct test proposals; each has 25 explicit WBS tasks.
- `academic_scheduler/panel_members_30.xlsx`: 30 panel members (8 Professors, 8 Doctors, 7 Lecturers, 7 Instructors).
- `academic_scheduler/hall_locations_8.xlsx`: 8 physical hall locations.
- `progress_evidence_R26-IT-095/submission_documents/`: five task-aligned sample submissions for the supplied source proposal.
- `progress_evidence_R26-IT-095/github_repo_R26-IT-095/`: ready-to-push local Git repository with 13 realistic commits.
- `progress_evidence_R26-IT-095/webhook_payloads/`: sample GitHub push payloads using the repository's real local commit SHAs.
- `progress_evidence_R26-IT-095\R26-IT-095_task_evidence_manifest.xlsx`: mapping of all 27 source tasks to document, Git, or manual evidence.

## Proposal parser test

Upload each PDF through the scheduling proposal form. The expected Group IDs are R26-IT-101, R26-IT-102, and R26-IT-103. Each file is designed to extract at least 20 tasks. Do not use these synthetic groups as production records.

## Academic-event scheduler test

1. Sign in as Academic Staff.
2. Upload `panel_members_30.xlsx` in Step 1 and `hall_locations_8.xlsx` in Step 2.
3. Use Project Start Date `2026-09-01` and event weeks Proposal=2, PP1=8, PP2=14, Viva=20.
4. All sample people and halls are available on the matching dates from 08:00 to 18:00.
5. The staff-role distribution supports the required panel: two Professor/Doctor members, one Lecturer, and one Instructor.

Uploading a workbook marks previous staff or halls inactive. Use only in a test database or re-upload your real workbook afterward.

## Document progress test for R26-IT-095

1. Generate and workload-balance the supplied `Proposal Reort Merged Final (1) (1).pdf` proposal first.
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
