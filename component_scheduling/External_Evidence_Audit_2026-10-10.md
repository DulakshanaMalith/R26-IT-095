# External-evidence audit — 10 October 2026

This note records a read-only cross-check of the public GitHub repository against the existing Scheduling PostgreSQL database. No commit, webhook, repository setting or original database row was changed during this audit.

## Public GitHub commit and local record

GitHub's public repository API reported `ModithaDilshan/test-repo` as public with default branch `main`. It returned the existing commit [`fb54899b9acdc5bcaee8e50af467969eeeec7757`](https://github.com/ModithaDilshan/test-repo/commit/fb54899b9acdc5bcaee8e50af467969eeeec7757), authored by `ModithaDilshan` at `2026-08-31T19:28:24Z` (1 September 2026, 00:58:24 Sri Lanka time), with message `[R26-IT-095-TASK-009] Revalidate assignment-aware webhook tracking`.

Read-only queries of the original `ipms_scheduling` PostgreSQL database returned:

| Record | Observed value |
|---|---|
| Repository registration for `R26-IT-095` | `https://github.com/ModithaDilshan/test-repo.git`; normalized name `modithadilshan/test-repo` |
| `github_commits` | Same full SHA, task ID `9`, evidence status `LINKED`, mapped student ID `IT22117014`, commit time `2026-09-01T00:58:24+05:30` |
| `github_webhook_deliveries` | Existing `push` delivery `2424dbbc-a572-11f1-9df8-9e149bdb5b50` recorded at approximately `2026-09-01T00:58:29+05:30`; an earlier `ping` delivery is also recorded |

The public SHA, task-keyed message and timestamp match the local linked evidence. This supports the claim that **a real public GitHub commit is represented in the Scheduling progress database**. The local `push` row is consistent with webhook ingestion. It is not independent proof of GitHub's server-to-server delivery response: [GitHub says webhook delivery details require repository administration access](https://docs.github.com/en/webhooks/testing-and-troubleshooting-webhooks/viewing-webhook-deliveries), which was not available through the public repository. The `LINKED` status is the application's assignment/identity decision, not proof that the code task was completed; the commit begins progress evidence only.

## Remaining external confirmations

- An approved university record for the exact registered name/title was not provided. The owner's message supplies `Lekamge R.L.M.D.`, `IT22117014`, and *Adaptive Scheduling and Generative Project Planning* (spelling normalised), but is not an institutional registration record.
- A team-approved individual/shared contribution statement was not provided. It cannot be inferred from file authorship or commits.
- The Team Formation sample API response still uses `P01`–`P03`/`SIM-*` identifiers; no matching backend group import to Scheduling group `R26-IT-095` was demonstrated.
- No direct Quality/Risk → Scheduling payload with a matching group ID was demonstrated. Portal navigation does not establish data exchange.
- The new local PDF upload/approval/webhook test is synthetic; this public commit and local webhook record predate that test. A single fresh real student upload → supervisor decision → GitHub.com delivery → downstream component trace remains uncollected.
- No formal supervisor/student usability study or real-cohort outcome study was supplied. Report this as a limitation.

For a definitive GitHub delivery receipt, a repository administrator should provide a redacted Recent Deliveries export or screenshot showing the `push` request and successful response for the delivery ID above. Do not include the webhook secret, authorization headers, private document bytes or student-identifying material beyond what the institution permits.
