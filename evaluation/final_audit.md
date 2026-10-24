# Independent final audit

The current run uses only participant-facing files under `dataset/`. `sample_output.csv` is read by evaluation code, not by the prediction engine. The official archive reports are `evaluation/evaluation_report.md` and `evaluation/usage_report.md`; copies under `code/evaluation/` are provided for the requested review path.

## Measured outcome

| Measure | Prior commit | Final run |
| --- | ---: | ---: |
| Public sample status | 32/32 | 32/32 |
| Exact step arrays | 15/32 | 15/32 |
| Position-aligned fields | 1012/1351 | 1012/1351 |
| Strict errors | 0 | 0 |
| Strict warnings | 1 | 1 |
| Regression tests | 19 passed | 23 passed |
| Full output rows | 518 | 518 |

The output CSV is byte-identical to the prior committed version. This pass strengthens the inference boundary and diagnostics; it does not manufacture an exact-sequence gain.

## Demonstrated repairs

- Snapshot `updated_at` metadata no longer enters the subject identifier index. Two unrelated users with the same name no longer share that name as a matching key.
- A short catalog alias such as `user_17` cannot make an unrelated PDF appear to contain the linked tombstone. Short aliases require the evidence manifest's `origin` to match the catalog target system.
- The sample mismatch report now has a machine-readable JSON companion with identity, history, expected and actual steps, relevant observations, and root causes.
- The `case_63` catalog/screenshot conflict remains a deterministic validator warning and has a regression test.

## Unresolved exact-array mismatches

`case_03`, `case_04`, `case_09`, `case_18`, `case_20`, `case_21`, `case_22`, `case_23`, `case_24`, `case_25`, `case_26`, `case_27`, `case_28`, `case_29`, `case_30`, `case_31`, `case_32`.

The 17 cases collectively lack 15 account-absence checks, six anonymized analytics checks, and seven retained audit checks; these categories overlap by case. The missing observations often exist, but their compliant state has removed direct identifiers. The participant files inspected do not provide a unique, explicit subject-to-resource chain for each missing resource. The planner must not use case numbering, name similarity, or competing timestamp candidates as a substitute. See `evaluation/mismatch_analysis.json` for each case's observations and exact fields.

## Remaining factual uncertainty

`case_63` has a later catalog identity link to the deletion subject and an earlier screenshot of the same resource displaying another person's direct identifiers. The output treats the later catalog mapping as current and the screenshot as proof the resource exists. A post-link snapshot or reliable reassignment history is absent. Strict validation can confirm the citation and format, but cannot settle the catalog's factual accuracy.

The existing uniquely timed activity fallbacks for account and analytics verification are weaker than direct identity or catalog links. They require a later state artifact, yet the temporal association itself remains an assumption that could fail on hidden cases. Removing them in a controlled comparison reduced exact public arrays from 15/32 to 9/32 without changing status accuracy; keeping them preserves the best measured output, while this limitation is disclosed.

## Submission boundaries

The included OCR cache is a deterministic transcription of participant-facing screenshots, used because standard-library Python cannot perform OCR and optional macOS Vision or Tesseract may not be available in the evaluator. It contains no organizer-only labels or golden answers. The archive excludes `dataset/`, Git internals, credentials, environments, and nested archives. Reproduction requires placing the supplied participant `dataset/` beside the extracted `code/` directory.
