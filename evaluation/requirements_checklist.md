# Requirements audit

Official source: `AGENTS.md` §6 and `problem_statement.md`. The pasted development prompt requested reports inside `code/evaluation/`; official instructions require them at archive-root `evaluation/`. Both locations are populated for review.

| Requirement | Source | Implementation | Validation | Status / correction |
| --- | --- | --- | --- | --- |
| One row for each of 518 cases, sorted | AGENTS §6.3 | `code/main.py:main` | `code/evaluation/validate.py` | Pass |
| Exact CSV schema and JSON step fields | AGENTS §6.3 | `main`, `step` | Strict validator | Pass |
| Non-deletion requests return `NOT_APPLICABLE` and `[]` | AGENTS §6.5 | `request_deletion`, `audit` | Public samples and `test_non_deletion_intents` | Pass on tested cases; multilingual and ambiguous hidden requests remain unverified |
| Current and historical identity | AGENTS §6.1, §6.5 | `identity`, `audit` | Historical-email synthetic test | Partial: ambiguous shared identifiers are not exhaustively resolved |
| Participant evidence formats | AGENTS §6.1, §6.6 | `evidence`, `image_text`, `state` | Public sample and format inspection | Partial: parser/OCR coverage is best effort |
| `audit_at` cutoff | AGENTS §6.2, §6.6 | `audit` | Strict citation-time check and future-cutoff case | Pass for cited timestamps; historical state inference remains partial |
| Policy, tombstones, retained records | AGENTS §6.5 | `policy_actions`, `category`, `audit` | Synthetic support and tombstone tests | Partial: some compliant records lack subject links |
| Active flow and restore risk | AGENTS §6.5 | `state`, `audit` | Synthetic flow and restore tests | Pass on tested cases; hidden process variants unverified |
| Evidence-backed findings/complete checks | AGENTS §6.6 | `catalog_links`, `evidence`, `audit`, `validate` | Strict validator and four-case regression test | Pass structurally; `case_63` identity evidence remains substantively disputed |
| Future actions have empty evidence IDs | AGENTS §6.6 | `audit` | Strict validator | Pass |
| Phase/operation/state/order | AGENTS §6.3–6.4 | `OPS`, `ORDER`, `PHASE`, `audit` | Strict validator | Pass |
| Public sample evaluation and custom cases | AGENTS §6.8 | `code/evaluation/main.py`, `code/tests/test_cases.py` | 32 samples, 19 tests, 3 extra checks | Pass as evaluation deliverable; 15/32 exact arrays remain |
| Model usage report | AGENTS §6.8 | `evaluation/usage_report.md` | Final run inspection | Pass: 0 runtime model calls |
| Archive contents and exclusions | AGENTS §6.9 | `code.zip` | ZIP listing and clean-run reproduction | Recheck after final packaging |
| Root append-only transcript | AGENTS §2, §5 | `log.txt` | Entry review and metadata check | Current turn entry required before final commit |
| Commit and authorized push | User request | Git | Local/remote head verification | Pending final commit |

The machine-readable full-output contract check is `evaluation/validation_report.json`. It currently reports zero mandatory structural errors and one warning. The catalog/screenshot identity conflict in `case_63` is documented in `evaluation/four_case_trace.md`; structural validation cannot decide that factual dispute.
