"""Detailed, reproducible diagnosis of the public sample only."""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'code'))
import main

def describe(step):
 return f"{step['operation']}@{step['system_id']}/{step['resource_id']} [{step['state']}; {step['evidence_id'] or 'future'}]"

def cause(missing):
 ops={s['operation'] for s in missing}
 causes=[]
 if 'VERIFY_RECORD_ABSENT' in ops:causes.append('Absent account resource lacks a grounded subject link')
 if 'VERIFY_RECORD_ANONYMIZED' in ops:causes.append('Anonymized analytics resource lost direct identifiers')
 if 'VERIFY_RECORD_PRESENT' in ops:causes.append('Retained audit resource lacks a grounded subject link')
 return '; '.join(causes) or 'Other step mismatch'

def write_report():
 ids,reverse=main.identity();evidence=main.evidence()
 gold={r['case_id']:r for r in main.read('sample_output.csv')}
 rows=[];groups=Counter()
 for request in main.read('sample_deletion_requests.csv'):
  predicted,actual=main.audit(request,ids,reverse,evidence)
  expected=json.loads(gold[request['case_id']]['steps_json'])
  if actual==expected:continue
  identity=lambda s:(s['operation'],s['system_id'],s['resource_id'])
  exp_map={identity(s):s for s in expected};act_map={identity(s):s for s in actual}
  missing=[s for s in expected if identity(s) not in act_map]
  extra=[s for s in actual if identity(s) not in exp_map]
  common=set(exp_map)&set(act_map)
  wrong_states=[f"{k[0]}@{k[1]}/{k[2]}: {exp_map[k]['state']} vs {act_map[k]['state']}" for k in sorted(common) if exp_map[k]['state']!=act_map[k]['state']]
  wrong_evidence=[f"{k[0]}@{k[1]}/{k[2]}: {exp_map[k]['evidence_id']} vs {act_map[k]['evidence_id']}" for k in sorted(common) if exp_map[k]['evidence_id']!=act_map[k]['evidence_id']]
  misidentified=[f"{s['operation']}@{s['system_id']}/{s['resource_id']}" for s in extra if any(e['operation']==s['operation'] and e['system_id']==s['system_id'] for e in missing)]
  wrong_order=not missing and not extra and [identity(s) for s in expected]!=[identity(s) for s in actual]
  root=cause(missing);groups.update(root.split('; '))
  rows.append((request['case_id'],predicted,expected,actual,missing,extra,misidentified,wrong_states,wrong_evidence,wrong_order,root))
 lines=['# Public sample step mismatch analysis','',
        'This report is generated from `sample_output.csv` and the current `audit` function. It is evaluation only; the prediction engine does not read the public answers. All 17 baseline mismatches were missing steps, with no extra step, wrong state, wrong evidence ID on a matched resource, or pure sorting error. The table below is regenerated after each evaluation.','',
        '## Shared causes and safe corrections','',
        '| Cause | Affected mismatches | Evidence needed for a safe correction |','| --- | ---: | --- |']
 for name,count in groups.most_common():
  correction={'Absent account resource lacks a grounded subject link':'A prior subject-to-account resource link and a later complete lookup or snapshot.',
              'Anonymized analytics resource lost direct identifiers':'A prior subject-to-analytics resource link plus a later anonymized snapshot.',
              'Retained audit resource lacks a grounded subject link':'A subject-bearing audit row or catalog link establishing the retained record.'}.get(name,'Grounded participant evidence.')
  lines.append(f'| {name} | {count} | {correction} |')
 lines+=['','No resource is assigned from proximity, case numbering, or a workflow result alone when multiple candidates exist. A unique nearby operation may locate a resource only when a later artifact proves its state.','',
         '## Per-case comparison','',
         '| Case | Expected operations | Actual operations | Missing steps | Extra steps | Incorrect IDs | Wrong states | Wrong evidence | Wrong order | Root cause / shared correction |',
         '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
 fmt=lambda values:'<br>'.join(values) if values else '—'
 for cid,status,expected,actual,missing,extra,wrong_ids,wrong_states,wrong_evidence,wrong_order,root in rows:
  lines.append('| '+ ' | '.join((cid,fmt([s['operation'] for s in expected]),fmt([s['operation'] for s in actual]),
                                fmt([describe(s) for s in missing]),fmt([describe(s) for s in extra]),fmt(wrong_ids),
                                fmt(wrong_states),fmt(wrong_evidence),'yes' if wrong_order else 'no',root))+' |')
 lines+=['',f'**Current exact arrays:** {32-len(rows)}/32. **Current mismatches:** {len(rows)}.','']
 report=ROOT/'evaluation'/'mismatch_analysis.md';report.write_text('\n'.join(lines),encoding='utf-8')
 (ROOT/'code'/'evaluation'/'mismatch_analysis.md').write_text('\n'.join(lines),encoding='utf-8')
 return {'exact':32-len(rows),'mismatches':len(rows),'groups':dict(groups)}

if __name__=='__main__':print(write_report())
