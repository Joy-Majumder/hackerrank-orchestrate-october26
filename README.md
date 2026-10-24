# Ghost Data Still Exists: deletion audit agent

This submission audits the 518 participant-facing requests in `dataset/deletion_requests.csv` and writes `output.csv` at the repository root. It uses only Python 3 standard-library modules and the supplied `dataset/` files. No credentials or network access are required.

## Run

From the repository root, with Python 3.10 or later:

```sh
python3 code/main.py
python3 -m unittest discover -s code/tests -v
python3 code/evaluation/main.py
python3 code/evaluation/validate.py
```

The first command writes the 518-row submission. The unittest suite covers synthetic edge cases and the four previously unproven requests. The evaluator compares all 32 public examples, runs three additional checks, and writes the reports at both `evaluation/` (the official archive location) and `code/evaluation/`. The strict validator writes `evaluation/validation_report.json` and exits nonzero for any mandatory contract error. The current full run passes with zero reported contract errors.

## Approach

The agent resolves current and historical names, emails, phone numbers, email hashes, and stable user IDs. It reads JSON exports and snapshots, executes SQL snapshots in an in-memory SQLite database, correlates several log formats by trace ID, parses handover text, extracts text from ReportLab PDF streams, and reads cached OCR transcriptions of the supplied screenshots. The OCR cache in `code/ocr_cache.py` contains participant-facing evidence text, not answers; `code/ocr.swift` can regenerate it on macOS with `WRITE_OCR_CACHE=1 python3 code/main.py`. It ignores evidence captured after each request's `audit_at`. A policy planner emits ordered findings, remediation, and verification steps. It never treats a workflow's reported status as proof of deletion.

The implementation has no runtime model calls. Its strength is deterministic, local evidence processing; its known limitation is that some anonymized, absent, or retained records lack explicit subject links in parsed evidence. Catalog identity links and independently observed artifacts resolve four formerly empty `COMPLETE` cases. The public sample has 32/32 correct statuses and 15/32 exact step arrays; 17 step arrays still differ. The remaining uniquely timed activity links are weaker than explicit identity links and may affect hidden accuracy. See `evaluation/evaluation_report.md`, `evaluation/mismatch_analysis.md` and its JSON companion, `evaluation/four_case_trace.md`, and `evaluation/final_audit.md` for measured results and evidence limits, `evaluation/requirements_checklist.md` for the official contract mapping, and `code/evaluation/interview_preparation.md` for grounded interview answers.

## Submission files

- `output.csv`: completed 518-case prediction file.
- `code.zip`: source, this README, official root evaluation reports, strict validation output, checklist, and interview preparation. The dataset is excluded. Place the supplied `dataset/` beside `code/` after extracting to run the archive.
- `log.txt`: coding-agent conversation summary for the `chat_transcript` slot.
- `agent-trace.zip`: full relevant harness trace, if available, following `agent_trace_instructions.md`. It should be prepared after the session finishes so its files are complete; review it for secrets before sharing.

Create `code.zip` from the repository root with `zip -r -FS code.zip README.md INTERVIEW_NOTES.md code evaluation -x '*/__pycache__/*' '*.pyc'`. Do not include `dataset/`, credentials, dependency caches, or nested archives. `code/ocr_cache.py` is the required participant-screenshot transcription used for a reproducible run.
