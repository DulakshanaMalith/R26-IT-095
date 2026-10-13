# Test Data Pack Validation Report

Generated and validated on 2026-08-31 against the current scheduling component.

## Proposal PDFs

| File | Detected Group ID | Tasks returned by actual WBS extractor | Result |
|---|---:|---:|---|
| R26-IT-101_Test_Proposal.pdf | R26-IT-101 | 24 | Pass |
| R26-IT-102_Test_Proposal.pdf | R26-IT-102 | 24 | Pass |
| R26-IT-103_Test_Proposal.pdf | R26-IT-103 | 25 | Pass |

Each proposal contains 25 explicit WBS entries and exceeds the requested minimum of 20 accepted tasks.

## Academic scheduler workbooks

- Panel workbook: 30 valid rows and the exact six-column upload schema.
- Role distribution: 8 Professors, 8 Doctors, 7 Lecturers, and 7 Instructors.
- Hall workbook: 8 physical halls and the exact five-column upload schema.
- All dates parse through the component's `_parse_dates` function.
- All time ranges parse as `08:00-18:00` through `_parse_time_range`.
- The pool supports panels containing two Professor/Doctor members, one Lecturer, and one Instructor.

## Progress evidence

- Five readable PDF/DOCX submissions align with current R26-IT-095 document task IDs 002, 012, 013, 026, and 027.
- The evidence manifest covers all 27 source-proposal tasks.
- The local Git repository passes `git fsck`, has a clean working tree, and contains 13 commits.
- Every commit message matches the backend's explicit task-reference regular expression.
- Four synthetic GitHub identities are mapped to the four R26-IT-095 student IDs.
- Three push-event JSON fixtures use commit SHAs from the generated repository.

No files were uploaded to PostgreSQL and no external GitHub repository was created during generation.
