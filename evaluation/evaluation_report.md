# Evaluation report

## Public sample (32 cases)

| Metric | Result |
| --- | ---: |
| Case-level deletion-status accuracy | 32/32 (100.0%) |
| Exact step-array accuracy | 15/32 (46.9%) |
| Position-aligned step-level accuracy | 126/193 (65.3%) |
| Position-aligned field-level accuracy | 1010/1351 (74.8%) |
| Operation-sequence accuracy | 15/32 (46.9%) |
| Full-run COMPLETE rows with no verification steps | 8 |

Step and field denominators use the longer of prediction and reference for each case; missing steps receive no credit. The public sample is the only source of reference answers. Hidden evaluation accuracy is unknown.

## Additional participant-created cases

| Case | Result |
| --- | --- |
| access request is not deletion | PASS |
| historical email resolves to stable user | PASS |
| future evidence excluded | PASS |

## Failures and improvements

The first parser missed handover rows, trace-linked log events, SQL JSON payloads, PDF attachments, and screenshots. The implementation now parses those formats, caches OCR text from participant-facing images, recovers historical identifiers, and filters evidence by audit time. Public-sample status accuracy improved to 32/32. Exact step arrays still differ in 17 cases, chiefly because compliant absent, anonymized, and retained records can lack an explicit subject identifier in the parsed evidence. Additionally, 8 full-run COMPLETE rows have no verification step; they cannot be treated as proven complete under the challenge contract. These are unresolved scoring risks. The engine does not substitute workflow claims for proof.

Structural validation passed for all 518 output rows, schema, order, operation/state pairs, and cited evidence timestamps. Structural validity does not establish substantive correctness.
