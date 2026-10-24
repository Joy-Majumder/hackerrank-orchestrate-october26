# AI interview notes

## What the program does

`code/main.py` loads requests, identity snapshots and history, policy rules, activity, and participant-visible evidence. It extracts records from JSON, SQL, logs, handover text, PDFs, and cached screenshot OCR. It links records to a subject through stable IDs and current or historical identifiers, selects observations available by `audit_at`, then emits ordered findings, remediation, and verification steps.

## Design decisions

- Workflow status and operation results are claims. Findings use evidence files, while uniquely timed activity is used only to help identify a resource for a later snapshot check.
- SQL exports run in an in-memory SQLite database. JSON payload columns are parsed so replicas and nested direct identifiers can be inspected.
- Policy actions come from `dataset/deletion_rules.csv`. Active flows and restore paths are disabled or blocked before record changes. Output order follows the required operation order.
- OCR text in `code/ocr_cache.py` was extracted from supplied participant-facing screenshots; it is included for a reproducible run on machines without macOS Vision.
- The final runtime makes no LLM calls, so measured model tokens and API cost are zero. This is a deterministic evidence agent, with development performed using Codex.

## Evaluation and limitations

Run `python3 code/main.py` and `python3 code/evaluation/main.py`. The public sample measures status, exact steps, position-aligned steps and fields, and operation sequence. The evaluator also checks all 518 output rows and three additional cases.

The status result on the 32 public samples is strong, but step recall is materially lower. Some absent, anonymized, and retained records cannot be linked to a subject from the parsed evidence. Several full-run `COMPLETE` rows lack an evidence-backed verification step. These are unresolved and should be described honestly in the interview; the hidden score cannot be predicted.
