"""Public-sample evaluation and submission validation."""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'code'))
import main

def evaluate():
 ids,reverse=main.identity();evidence=main.evidence()
 gold={r['case_id']:r for r in main.read('sample_output.csv')}
 samples=main.read('sample_deletion_requests.csv')
 status=exact=sequence=step_hits=step_total=field_hits=field_total=0
 fields=('step_no','phase','system_id','resource_id','operation','state','evidence_id')
 failures=[]
 for request in samples:
  predicted,steps=main.audit(request,ids,reverse,evidence)
  expected=gold[request['case_id']];target=json.loads(expected['steps_json'])
  status+=predicted==expected['deletion_status'];exact+=steps==target
  sequence+=[s['operation'] for s in steps]==[s['operation'] for s in target]
  step_total+=max(len(steps),len(target));step_hits+=sum(a==b for a,b in zip(steps,target))
  field_total+=max(len(steps),len(target))*len(fields)
  field_hits+=sum(a.get(k)==b.get(k) for a,b in zip(steps,target) for k in fields)
  if steps!=target:failures.append(request['case_id'])
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
 unproven_complete=sum(row['deletion_status']=='COMPLETE' and not json.loads(row['steps_json']) for row in output)
 custom=[]
 seed=dict(samples[4]);seed['request_text']='Please send me a copy of my information.'
 custom.append(('access request is not deletion',main.audit(seed,ids,reverse,evidence)==('NOT_APPLICABLE',[])))
 audit=main.read('user_audit_log.csv');old=next((x for x in audit if x['field_name']=='email' and x['old_value']),None)
 custom.append(('historical email resolves to stable user',old is not None and old['user_id'] in reverse.get(old['old_value'].casefold(),set())))
 early=dict(samples[4]);early['audit_at']='2026-01-01T00:00:00Z';_,early_steps=main.audit(early,ids,reverse,evidence)
 custom.append(('future evidence excluded',all(not s['evidence_id'] or known[s['evidence_id']]<=early['audit_at'] for s in early_steps)))
 assert all(result for _,result in custom)
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
| Full-run COMPLETE rows with no verification steps | {unproven_complete} |

Step and field denominators use the longer of prediction and reference for each case; missing steps receive no credit. The public sample is the only source of reference answers. Hidden evaluation accuracy is unknown.

## Additional participant-created cases

| Case | Result |
| --- | --- |
'''+''.join(f'| {name} | {"PASS" if result else "FAIL"} |\n' for name,result in custom)+f'''
## Failures and improvements

The first parser missed handover rows, trace-linked log events, SQL JSON payloads, PDF attachments, and screenshots. The implementation now parses those formats, caches OCR text from participant-facing images, recovers historical identifiers, and filters evidence by audit time. Public-sample status accuracy improved to {status}/32. Exact step arrays still differ in {len(failures)} cases, chiefly because compliant absent, anonymized, and retained records can lack an explicit subject identifier in the parsed evidence. Additionally, {unproven_complete} full-run COMPLETE rows have no verification step; they cannot be treated as proven complete under the challenge contract. These are unresolved scoring risks. The engine does not substitute workflow claims for proof.

Structural validation passed for all 518 output rows, schema, order, operation/state pairs, and cited evidence timestamps. Structural validity does not establish substantive correctness.
''',encoding='utf-8')
 usage=ROOT/'evaluation'/'usage_report.md'
 usage.write_text('''# Model usage report

Final full-dataset run: `python3 code/main.py`; 518 requests. The runtime uses deterministic local parsers and policy logic.

| Provider | Model | Calls | Input tokens | Output tokens | Total tokens | Estimated cost |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| None | None | 0 | 0 | 0 | 0 | $0.00 |
| **Overall** | | **0** | **0** | **0** | **0** | **$0.00** |

Average model tokens per request: 0 input, 0 output, 0 total. Estimated model cost per request: $0.00. Development-session model usage is outside the final runtime and is not available as a reliable token count.
''',encoding='utf-8')
 print('sample status',status,'/32; exact arrays',exact,'/32; output rows',len(output))

if __name__=='__main__':evaluate()
