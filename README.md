# Ghost Data Still Exists: deletion audit agent

This submission audits the 518 participant-facing requests in `dataset/deletion_requests.csv` and writes `output.csv` at the repository root. It uses only Python 3 standard-library modules and the supplied `dataset/` files. No credentials or network access are required.

## Run

From the repository root, with Python 3.10 or later:

```sh
python3 code/main.py
python3 code/evaluation/main.py
```

The first command writes the 518-row submission. The second checks schema, ordering, evidence IDs and timestamps, compares all 32 public examples, runs three additional checks, and writes `evaluation/evaluation_report.md` and `evaluation/usage_report.md`.

## Approach

The agent resolves current and historical names, emails, phone numbers, email hashes, and stable user IDs. It reads JSON exports and snapshots, executes SQL snapshots in an in-memory SQLite database, correlates several log formats by trace ID, parses handover text, extracts text from ReportLab PDF streams, and reads cached OCR transcriptions of the supplied screenshots. The OCR cache in `code/ocr_cache.py` contains participant-facing evidence text, not answers; `code/ocr.swift` can regenerate it on macOS with `WRITE_OCR_CACHE=1 python3 code/main.py`. It ignores evidence captured after each request's `audit_at`. A policy planner emits ordered findings, remediation, and verification steps. It never treats a workflow's reported status as proof of deletion.

The implementation has no runtime model calls. Its strength is deterministic, local evidence processing; its known limitation is that some anonymized, absent, or retained records lack explicit subject links in parsed evidence. Some `COMPLETE` rows have no verification step, so they are not proven complete under the challenge contract. See the measured public-sample results and unresolved risks in `evaluation/evaluation_report.md`.

## Submission files

- `output.csv`: completed 518-case prediction file.
- `code.zip`: source, this README, and both Markdown evaluation reports. The dataset is excluded.
- `log.txt`: coding-agent conversation summary for the `chat_transcript` slot.
- `agent-trace.zip`: full relevant harness trace, if available, following `agent_trace_instructions.md`. It should be prepared after the session finishes so its files are complete; review it for secrets before sharing.

Create `code.zip` from the repository root with `zip -r code.zip README.md code evaluation -x '*/__pycache__/*' '*.pyc'`. Do not include `dataset/`, credentials, caches, or nested archives.
