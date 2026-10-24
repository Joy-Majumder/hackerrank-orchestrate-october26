"""Public-sample evaluation and submission validation."""
import csv
import json
import sys
import subprocess
import shutil
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'code'))
import main
from validate import validate
from mismatch_report import write_report

def evaluate():
 ids,reverse=main.identity();evidence=main.evidence()
 gold={r['case_id']:r for r in main.read('sample_output.csv')}
 samples=main.read('sample_deletion_requests.csv')
 status=exact=sequence=step_hits=step_total=field_hits=field_total=0
 true_steps=predicted_steps=reference_steps=operation_hits=state_hits=evidence_hits=0
 fields=('step_no','phase','system_id','resource_id','operation','state','evidence_id')
 failures=[];mismatches=[]
 for request in samples:
  predicted,steps=main.audit(request,ids,reverse,evidence)
  expected=gold[request['case_id']];target=json.loads(expected['steps_json'])
  status+=predicted==expected['deletion_status'];exact+=steps==target
  sequence+=[s['operation'] for s in steps]==[s['operation'] for s in target]
  step_total+=max(len(steps),len(target));step_hits+=sum(a==b for a,b in zip(steps,target))
  field_total+=max(len(steps),len(target))*len(fields)
  field_hits+=sum(a.get(k)==b.get(k) for a,b in zip(steps,target) for k in fields)
  predicted_steps+=len(steps);reference_steps+=len(target)
  signature=lambda s:tuple(s[k] for k in fields if k!='step_no')
  true_steps+=sum((Counter(map(signature,steps))&Counter(map(signature,target))).values())
  operation_hits+=sum(a['operation']==b['operation'] for a,b in zip(steps,target))
  state_hits+=sum(a['state']==b['state'] for a,b in zip(steps,target))
  evidence_hits+=sum(a['evidence_id']==b['evidence_id'] for a,b in zip(steps,target))
  if steps!=target:
   failures.append(request['case_id'])
   key=lambda s:(s['operation'],s['system_id'],s['resource_id'])
   pc=Counter(map(key,steps));gc=Counter(map(key,target))
   missing=list((gc-pc).elements());extra=list((pc-gc).elements())
   mismatches.append((request['case_id'],expected['deletion_status'],predicted,missing,extra,
                      sum(a['evidence_id']!=b['evidence_id'] for a,b in zip(steps,target) if key(a)==key(b))))
 cases=main.read('deletion_requests.csv')
 with (ROOT/'output.csv').open(newline='',encoding='utf-8') as f:output=list(csv.DictReader(f))
 assert len(cases)==len(output)==518
 assert [r['case_id'] for r in output]==sorted(r['case_id'] for r in cases)
 known={r['file_id']:r['captured_at'] for r in main.read('evidence_files.csv')}
 known.update({r['activity_id']:r['event_time'] for r in main.read('system_activity.csv')})
 known.update({r['audit_id']:r['event_time'] for r in main.read('user_audit_log.csv')})
 by_case={r['case_id']:r for r in cases}
 for row in output:
  assert row['deletion_status'] in ('COMPLETE','INCOMPLETE','NOT_APPLICABLE')
  steps=json.loads(row['steps_json']);assert isinstance(steps,list)
  assert row['deletion_status']!='NOT_APPLICABLE' or not steps
  assert [s['step_no'] for s in steps]==list(range(1,len(steps)+1))
  assert all(set(s)==set(fields) and s['operation'] in main.OPS and (s['phase'],s['state'])==main.OPS[s['operation']] for s in steps)
  assert steps==sorted(steps,key=lambda s:(main.PHASE[s['phase']],main.ORDER[s['operation']],s['system_id'],s['resource_id']))
  for s in steps:
   if s['evidence_id']:assert s['evidence_id'] in known and known[s['evidence_id']]<=by_case[row['case_id']]['audit_at']
   if row['deletion_status']=='INCOMPLETE' and s['phase']!='FINDING':assert not s['evidence_id']
 validation=validate()
 mismatch_detail=write_report()
 unproven_complete=sum(row['deletion_status']=='COMPLETE' and not json.loads(row['steps_json']) for row in output)
 custom=[]
 seed=dict(samples[4]);seed['request_text']='Please send me a copy of my information.'
 access_observed=main.audit(seed,ids,reverse,evidence)
 custom.append(('Access request',seed['request_text'],'NOT_APPLICABLE; 0 steps',f'{access_observed[0]}; {len(access_observed[1])} steps',access_observed==('NOT_APPLICABLE',[])))
 audit=main.read('user_audit_log.csv');old=next((x for x in audit if x['field_name']=='email' and x['old_value']),None)
 old_resolved=old is not None and old['user_id'] in reverse.get(old['old_value'].casefold(),set())
 custom.append(('Historical email','Old email from participant audit history','Stable user resolves', 'Stable user resolves' if old_resolved else 'No match',old_resolved))
 early=dict(samples[4]);early['audit_at']='2026-01-01T00:00:00Z';_,early_steps=main.audit(early,ids,reverse,evidence)
 future_excluded=all(not s['evidence_id'] or known[s['evidence_id']]<=early['audit_at'] for s in early_steps)
 custom.append(('Future cutoff','Sample request with audit_at set to 2026-01-01','No citation after cutoff','No citation after cutoff' if future_excluded else 'Late citation found',future_excluded))
 assert all(result for *_,result in custom)
 test_run=subprocess.run([sys.executable,'-m','unittest','discover','-s','code/tests'],cwd=ROOT,capture_output=True,text=True)
 assert test_run.returncode==0,test_run.stderr
 test_count=int(__import__('re').search(r'Ran (\d+) tests',test_run.stderr).group(1))
 mismatch_rows=[]
 for case,expected_status,predicted_status,missing,extra,evidence_errors in mismatches:
  fmt=lambda items:', '.join(f'{op}@{sys}/{rid}' for op,sys,rid in items) or '—'
  cause='Missing linked verification evidence' if missing and all(x[0].startswith('VERIFY') for x in missing) and not extra else 'Policy or extraction mismatch'
  mismatch_rows.append(f'| {case} | {expected_status} / {predicted_status} | {fmt(missing)} | {fmt(extra)} | {evidence_errors} | {cause} |')
 report=ROOT/'evaluation'/'evaluation_report.md';report.parent.mkdir(exist_ok=True)
 report.write_text(f'''# Evaluation report

## Public sample (32 cases)

| Metric | Result |
| --- | ---: |
| Case-level deletion-status accuracy | {status}/32 ({status/32:.1%}) |
| Exact step-array accuracy | {exact}/32 ({exact/32:.1%}) |
| Position-aligned step-level accuracy | {step_hits}/{step_total} ({step_hits/step_total:.1%}) |
| Position-aligned field-level accuracy | {field_hits}/{field_total} ({field_hits/field_total:.1%}) |
| Operation-sequence accuracy | {sequence}/32 ({sequence/32:.1%}) |
| Step precision (exact fields except step number) | {true_steps}/{predicted_steps} ({true_steps/predicted_steps:.1%}) |
| Step recall (exact fields except step number) | {true_steps}/{reference_steps} ({true_steps/reference_steps:.1%}) |
| Position-aligned operation accuracy | {operation_hits}/{step_total} ({operation_hits/step_total:.1%}) |
| Position-aligned state accuracy | {state_hits}/{step_total} ({state_hits/step_total:.1%}) |
| Position-aligned evidence accuracy | {evidence_hits}/{step_total} ({evidence_hits/step_total:.1%}) |
| Full-run COMPLETE rows with no verification steps | {unproven_complete} |
| Full-run validator warnings | {validation['warning_count']} |

Step and field denominators use the longer of prediction and reference for each case; missing steps receive no credit. The public sample is the only source of reference answers. Hidden evaluation accuracy is unknown.

## Before and after this pass

| Measure | Previous committed run | Current run |
| --- | ---: | ---: |
| Status accuracy | 32/32 | {status}/32 |
| Exact step arrays | 15/32 | {exact}/32 |
| Position-aligned fields | 1012/1351 | {field_hits}/{field_total} |
| Strict validation errors | 0 | {validation['error_count']} |
| Strict validation warnings | 1 | {validation['warning_count']} |
| Regression tests | 19 passed | {test_count} passed |

The exact-array target did not improve. No expected sample array or case ID is used by the prediction engine; the reference file is read only here.

## Method and dataset

The public sample has 32 cases; the evaluation input has 518. The program uses identity snapshots and history, 4,011 activity rows, 15 policy rules, and 94 manifested evidence files. Each sample prediction is generated by the same `audit` function as the final CSV. Exact step precision and recall compare all step fields except `step_no` as a multiset; position-aligned metrics compare rows at the same array index.

`code/main.py` parses JSON, SQL, logs, PDF text, handover rows, and cached participant screenshot OCR into resource observations. Identity resolution combines the snapshot with historical changes but excludes snapshot timestamps and names shared by multiple subjects. Catalog events can link a resource or artifact alias to a subject; the cited artifact must separately establish state. Short user-ID aliases are restricted to matching source origins to avoid unrelated-document joins. The planner reads `deletion_rules.csv`, compares observed and required states, and orders findings, remediation, and checks.

State reconstruction excludes evidence captured or observed after `audit_at`, excludes bare lookup-start events, and does not treat operation success claims as state proof. Later eligible state observations supersede earlier ones; equal-time conflicts favor the exposed copy so replica drift is not hidden. The uniquely timed activity fallbacks for some account and analytics checks remain weaker associations than a direct identifier or catalog link; they are a hidden-score risk because timing alone cannot prove identity. The remaining catalog/screenshot disagreement is retained as a warning.

## Per-case public-sample mismatches

| Case | Expected / predicted status | Missing steps | Extra steps | Evidence mismatches at aligned keys | Likely cause |
| --- | --- | --- | --- | ---: | --- |
'''+('\n'.join(mismatch_rows) or '| None | — | — | — | 0 | — |')+f'''

The mismatch categories are derived from direct comparison with the public answers. A missing verification ID is not filled in by guessing a resource association. The full expected/actual operation and field comparison for all {mismatch_detail['mismatches']} mismatches is in `evaluation/mismatch_analysis.md`; machine-readable details are in `evaluation/mismatch_analysis.json`.

## Additional participant-created cases

| Case | Synthetic input | Expected | Observed | Result |
| --- | --- | --- | --- | --- |
'''+''.join(f'| {name} | {input_value} | {expected} | {observed} | {"PASS" if result else "FAIL"} |\n' for name,input_value,expected,observed,result in custom)+f'''
The independent `code/tests/test_cases.py` suite passed {test_count} executed tests covering historical email, evidence-only verification, catalog identity joins, timestamp conflicts, retained records, active flows, restore risks, ordering, and non-deletion requests. The observed assertions all passed.

## Failures and improvements

The first parser missed handover rows, trace-linked log events, SQL JSON payloads, PDF attachments, and screenshots. The implementation now parses those formats, caches OCR text from participant-facing images, recovers historical identifiers, and filters evidence by audit time. A later participant catalog link now connects artifact IDs to subjects while the artifact itself establishes state. This resolved four formerly unproven COMPLETE cases. Stricter citation-state validation exposed a wrong policy category for a catalog-linked tombstone; that mapping was repaired. This pass also prevented a short catalog alias from joining an unrelated PDF and removed snapshot metadata and shared names from subject matching. Public-sample status accuracy is {status}/32. Exact step arrays still differ in {len(failures)} cases, chiefly because compliant absent, anonymized, and retained records can lack an explicit subject identifier in the parsed evidence. {unproven_complete} full-run COMPLETE rows have no verification step. The engine does not substitute workflow operation results for proof.

Strict validation: **{'PASS' if validation['passed'] else 'FAIL'}**, {validation['error_count']} mandatory errors. The machine-readable details are in `evaluation/validation_report.json`. CSV shape, ordering, operation/state pairs, cited evidence timestamps, resource membership, and cited observable states were checked. Structural validity does not establish substantive correctness, especially for the conflicting `case_63` identity association documented in `evaluation/four_case_trace.md`.

## Reproduction

Run `python3 code/main.py`, `python3 -m unittest discover -s code/tests`, `python3 code/evaluation/main.py`, then `python3 code/evaluation/validate.py` from the repository root. The last command exits nonzero if mandatory validation errors exist.
''',encoding='utf-8')
 usage=ROOT/'evaluation'/'usage_report.md'
 usage.write_text('''# Model usage report

Final full-dataset run: `python3 code/main.py`; 518 requests. The runtime uses deterministic local parsers and policy logic.

| Provider | Model | Calls | Input tokens | Output tokens | Total tokens | Estimated cost |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| None | None | 0 | 0 | 0 | 0 | $0.00 |
| **Overall** | | **0** | **0** | **0** | **0** | **$0.00** |

Average model tokens per request: 0 input, 0 output, 0 total. Estimated model cost per request: $0.00. Development-session model usage is outside the final runtime and is not available as a reliable token count.

The included screenshot OCR text cache was generated before the final run from participant-facing images. It contains observations, not model answers. The final run read that cache and made zero provider calls. Cost estimates cover model API usage only; local CPU time is not priced.
''',encoding='utf-8')
 shutil.copyfile(report,ROOT/'code'/'evaluation'/'evaluation_report.md')
 shutil.copyfile(usage,ROOT/'code'/'evaluation'/'usage_report.md')
 print('sample status',status,'/32; exact arrays',exact,'/32; output rows',len(output))

if __name__=='__main__':evaluate()
