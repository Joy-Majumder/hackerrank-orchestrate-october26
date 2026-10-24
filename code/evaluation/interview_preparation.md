# AI judge interview preparation

Use these answers to describe the submitted implementation. The final **runtime** is deterministic Python and makes no model calls. Codex assisted development; the repository does not measure that development session's token usage. Public sample results are 32/32 statuses and 15/32 exact step arrays. Strict full-run validation reports zero structural errors; the `case_63` catalog/screenshot identity conflict and 17 sample step mismatches remain substantive risks. Do not claim a perfect result.

## Five-minute architecture explanation

1. **Input and decision (one minute).** `code/main.py:main` reads 518 requests. `request_deletion` screens non-deletion and negated requests before audit work. `identity` joins current identifiers and changes from the audit log. A historical email can resolve to the same stable user ID.
2. **Evidence (one minute).** `evidence` parses participant JSON, SQL snapshots, logs, PDFs, handover text, and cached screenshot OCR once. Each extracted observation keeps a resource, system, time, and file ID. Activity events help locate a resource but their success flags are not accepted as final-state proof.
3. **Temporal policy audit (one minute).** `audit` ignores evidence after `audit_at` and earlier than the request, chooses the latest linked observation per resource, interprets its state, and applies actions read from `deletion_rules.csv`. Tombstones keep their stable reference while direct identifiers must be redacted.
4. **Plan and validation (one minute).** Findings cite evidence. In incomplete cases, flow disabling and restore blocking precede record changes; future actions have empty evidence IDs. Verification proves completed states or specifies future checks. `validate.py` checks format and citations across all cases.
5. **Honest outcome (one minute).** The public sample reaches 100% status but 46.9% exact sequence accuracy. Four empty COMPLETE rows were repaired using catalog-to-artifact links. Some compliant or absent records still lack a subject link, and one later catalog link conflicts with an earlier screenshot, so hidden performance remains unknown.

## Ten-minute walkthrough: a remaining search copy

1. Show an authorized request and its `audit_at` in `dataset/sample_deletion_requests.csv`; explain that `reported_status` is only a claim.
2. Point to `identity()` and `user_audit_log.csv`: an old email and current email resolve to one `user_id`.
3. Point to `evidence()`: a search resource appears in a manifested participant file; its file ID becomes the citation.
4. Point to `audit()`: it filters on both capture and observation time, then uses the latest linked state for that resource.
5. Point to `category()` and `policy_actions()`: a search index entry has a DELETE requirement.
6. Trace `REPORT_REMAINING_RECORD` with `PRESENT`, `DELETE_RECORD` with `ABSENT`, and `VERIFY_RECORD_ABSENT` with `ABSENT`. The finding cites the existing file; future steps cite nothing.
7. Show `code/tests/test_cases.py:test_historical_email_remaining_in_search`, which asserts the operation sequence on synthetic participant-style input.
8. Explain ordering and `step_no` assignment after sorting. Show `output.csv` and `validate.py` checks.
9. Explain the limitation: when an absent resource has no explicit subject link, this approach can miss a valid verification step. The per-case public mismatch table shows that pattern.
10. End with reproduction commands in `README.md`, the measured report, zero structural validator errors, and the unresolved step and identity limits.

## Questions and grounded answers

For each answer, the **short** sentence is suitable for the first reply; expand with **detail** if asked. The file and example columns point to actual implementation or tests.

| # | Question | Short answer | Technical detail | File/function | Supporting example |
| ---: | --- | --- | --- | --- | --- |
| 1 | What problem is solved? | It audits whether deletion really completed. | The program identifies remaining personal data, exposed identifiers, live copies, and restoration paths at each case's audit time. | `code/main.py:audit` | Synthetic search copy test reports a remaining record. |
| 2 | Architecture? | Load, link, interpret, plan, serialize, validate. | CSV data and heterogeneous evidence are parsed once; per-case audits join identifiers and evidence, apply policy, and emit ordered steps. | `main`, `identity`, `evidence`, `audit` | `python3 code/main.py` writes 518 rows. |
| 3 | Why Python? | It runs locally with only the standard library. | `csv`, `json`, `sqlite3`, regex, and `zlib` cover the supplied formats; Python 3.10+ is documented. | `README.md`, `code/main.py` imports | In-memory SQLite reads SQL snapshots. |
| 4 | Why use AI? | The final runtime uses no model API. | Codex helped develop the code; local deterministic extraction makes evidence and output reproducible. This is not a claim that an LLM reasons over each case. | `evaluation/usage_report.md` | Final run: zero calls and tokens. |
| 5 | Which tasks are deterministic? | Parsing, joining, policy, ordering, and serialization. | The input dataset and cached OCR text are fixed; `audit` has no random sampling or model output. | `code/main.py` | Clean-run output can be byte-compared. |
| 6 | How does identity resolution work? | It maps current and former identifiers to stable user IDs. | `identity` indexes identity rows and old/new audit values; `audit` starts from request email and gathers the subject's known tokens. | `identity`, `audit` | Historical-email synthetic test. |
| 7 | Historical identifiers? | Both sides of each identity change enter the index. | `user_audit_log.csv` supplies old and new values, including old email addresses that can remain in other systems. | `identity` | Additional evaluation case checks old email lookup. |
| 8 | Heterogeneous evidence? | Each file is parsed into resource observations. | JSON records, SQLite exports, trace-correlated logs, PDF text streams, handover rows, and cached OCR are normalized with file ID and time. | `evidence`, `image_text` | SQL `record_json` is decoded after SQLite execution. |
| 9 | Resource state? | The latest linked observation before cutoff determines it. | `state` interprets explicit record fields and documented log response values; `audit` keeps the latest observation per system/resource. | `state`, `audit` | `restore_allowed=True` maps to active restore risk. |
| 10 | Meaning of `audit_at`? | It is the answer's evidence cutoff. | Both manifest capture time and observation time must be at or before it; later files cannot prove earlier completion. | `audit` | Future-cutoff custom evaluation case. |
| 11 | Conflicting evidence? | Prefer the later eligible observation per resource. | `audit` compares observation and capture times; an activity success claim alone does not override a snapshot of a remaining record. Cross-source conflicts can still be ambiguous. | `audit`, `nearby_account` | Account activity only locates an ID for snapshot inspection. |
| 12 | Retention policy? | Read category actions from the supplied rules. | `policy_actions` maps categories to DELETE, REDACT, ANONYMIZE, or RETAIN; `audit` emits the matching desired state. | `policy_actions`, `category`, `audit` | Security audit records are verified present. |
| 13 | Tombstones? | Keep stable reference; remove direct identifiers. | A tombstone with email is a redaction violation; one with only stable user ID receives a redacted verification. | `state`, `category`, `audit` | `test_tombstone_keeps_stable_reference_and_redacts_email`. |
| 14 | Active sync? | An enabled relevant flow is a recreation risk. | A linked integration resource in ACTIVE state produces a finding, `DISABLE_DATA_FLOW`, and `VERIFY_DATA_FLOW_DISABLED`. | `state`, `audit` | `test_active_sync_is_disabled_before_record_change`. |
| 15 | Restore risk? | An allowed relevant backup restore must be blocked. | Active backup state produces `REPORT_RESTORE_RISK`, `BLOCK_RESTORE`, and a future blocked check. | `state`, `audit` | `test_restore_risk_is_blocked`. |
| 16 | Findings? | A mismatched current and required state creates a cited finding. | The planner uses `REPORT_REMAINING_RECORD`, `REPORT_EXPOSED_PII`, or process-risk operations and carries the observed file ID. | `audit`, `step` | Search record found in synthetic evidence. |
| 17 | Remediation? | It follows policy and removes recreation paths first. | Current versus desired state selects delete, redact, anonymize, flow disable, or restore block. | `audit`, `OPS`, `ORDER` | Retained support message is redacted. |
| 18 | Verification? | Each considered resource gets its required final-state check. | In complete cases it cites observed proof; in incomplete cases it describes a future check with empty evidence ID. | `audit` | `VERIFY_RECORD_REDACTED` follows support redaction. |
| 19 | Why ordering? | Unsafe processes must stop before changing their copies. | All steps are sorted by phase and operation priority; step numbers are assigned only after sorting. | `ORDER`, `PHASE`, `audit` | Active sync test asserts disable before delete. |
| 20 | Evidence IDs? | Validator checks IDs and timestamps. | `validate.py` builds sets from manifest, activity, and audit IDs, rejects unknown or post-cutoff citations, and enforces empty IDs for future steps. | `code/evaluation/validate.py:validate` | `validation_report.json` currently records zero structural errors. |
| 21 | Hallucination prevention? | The runtime cannot generate arbitrary prose or IDs. | Allowed operations are an enum; finding citations come from parsed participant files; the validator checks each nonempty reference. | `OPS`, `evidence`, `validate` | No provider model call in final run. |
| 22 | Accuracy evaluation? | Compare public sample output, then validate every prediction. | `evaluation/main.py` measures status, exact arrays, operation sequence, position-aligned fields, and exact-step precision/recall. | `code/evaluation/main.py:evaluate` | 32 public cases and 518 output rows. |
| 23 | Sample result? | 32/32 statuses; 15/32 exact arrays. | Position-aligned field accuracy is 1012/1351 (74.9%); exact-step recall is 165/193 (85.5%). Hidden accuracy is unknown. | `evaluation/evaluation_report.md` | Detailed mismatch analysis lists 17 cases. |
| 24 | Errors fixed? | Negated intent and several evidence formats were repaired. | The audit now excludes “do not close” and similar non-deletion requests, parses nested SQL JSON, trace logs, PDFs, and screenshot text. | `request_deletion`, `evidence` | Four non-deletion phrasings in `test_non_deletion_intents`. |
| 25 | Custom cases? | Nineteen regression tests plus three evaluation checks. | They exercise historical email, catalog joins, pre-request identity links, conflicting snapshots and replicas, sync ordering, retention, tombstones, restore, negation, and future cutoffs. | `code/tests/test_cases.py`, `evaluation/main.py` | Nineteen unittest methods pass. |
| 26 | Model cost? | Zero final-runtime model cost. | No model providers are invoked: zero calls, input tokens, output tokens, and estimated API cost per request. Local compute is not costed. | `evaluation/usage_report.md` | 518-case run has 0 model tokens. |
| 27 | Scaling? | Parse evidence once, then scan observations per case. | With E observations and C cases the current join is roughly O(C×E); an inverted identity index would improve larger datasets. | `evidence`, `audit` | Current dataset has 94 files and 518 cases. |
| 28 | Limitations? | Some compliant or absent records lack a reliable subject link. | Exact public step arrays match only 15/32; a later catalog link for `case_63` conflicts with an earlier screenshot. | `evaluation/evaluation_report.md`, `evaluation/four_case_trace.md` | All four prior empty cases now have artifact-grounded findings. |
| 29 | Next improvement? | Add grounded reverse links for compliant resources. | Index subject-to-resource relationships from earlier participant evidence and event chains, with temporal proof; then rerun sample and strict checks. | `audit`, `nearby_account` | Missing account and anonymized analytics checks in public sample. |
| 30 | Demonstrate one case? | Walk the synthetic search copy end to end. | An old email resolves to the subject; linked search evidence shows PRESENT; DELETE policy yields finding, deletion, and absence verification. | `test_historical_email_remaining_in_search` | Exact sequence asserted in that test. |

## Hardest bug and what remains

Some SQL snapshots store a JSON object inside a row. Reading only SQL columns missed direct identifiers, so the parser now decodes `record_json` and merges its fields before identity matching. The regression suite and public sample were rerun after this change. The harder unresolved issue is **proof of absence**: absence cannot be linked to a person simply because a later snapshot lacks an email. The implementation uses a uniquely timed account activity to locate a resource and a later full snapshot to verify its absence; it still misses other compliant resources. Fabricating those links would improve apparent step counts while violating evidence rules.

## Challenging follow-ups

- How do you prove a negative when a snapshot does not identify the deleted subject? Answer: require a prior grounded subject-resource link plus a complete later snapshot; otherwise report uncertainty.
- Can a delayed replica or restore invalidate an earlier completion? Yes, if active by `audit_at`; inspect replica and restore evidence at the cutoff.
- Is a retained support message automatically compliant? No; its direct identifiers must satisfy the REDACT rule.
- Does 32/32 public status accuracy predict hidden score? No; step accuracy is lower and hidden cases are unseen.
- Is the system an AI-powered runtime agent? The submitted runtime is deterministic and uses no LLM. Explain that honestly and discuss where a validated semantic classifier or OCR model could help.
- Why was strict validation failing? Four cases were labelled COMPLETE because their identity links sat in catalog activity rather than inside the artifacts. The general link join now connects the real artifacts; structural validation reports zero errors. Explain the remaining `case_63` identity conflict honestly.
