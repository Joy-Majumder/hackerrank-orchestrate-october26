"""Strict output-contract validator; writes a machine-readable report."""
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'code'))
import main

FIELDS={'step_no','phase','system_id','resource_id','operation','state','evidence_id'}

def visible_identity_conflict(records,subject_keys):
 for record in records:
  visible=' '.join(str(record.get(k,'')) for k in ('image_text','document_text'))
  visible_emails={x.casefold() for x in re.findall(r'[\w.+-]+@[\w.-]+',visible)}
  if visible_emails and not visible_emails&subject_keys:return True
 return False

def validate():
 errors=[];warnings=[]
 def error(case,message):errors.append({'case_id':case,'message':message})
 requests=main.read('deletion_requests.csv')
 case_ids=[r['case_id'] for r in requests]
 req={r['case_id']:r for r in requests}
 ids_by_user,reverse=main.identity()
 with (ROOT/'output.csv').open(newline='',encoding='utf-8') as f:
  reader=csv.DictReader(f);header=reader.fieldnames;output=list(reader)
 if header!=['case_id','deletion_status','steps_json']:error('*','incorrect CSV header')
 if len(output)!=len(requests):error('*',f'expected {len(requests)} rows; found {len(output)}')
 ids=[r['case_id'] for r in output]
 if len(ids)!=len(set(ids)):error('*','duplicate case_id')
 if set(ids)!=set(case_ids):error('*','missing or additional case_id')
 if ids!=sorted(ids):error('*','case rows are not sorted')
 known={r['file_id']:r['captured_at'] for r in main.read('evidence_files.csv')}
 known.update({r['activity_id']:r['event_time'] for r in main.read('system_activity.csv')})
 known.update({r['audit_id']:r['event_time'] for r in main.read('user_audit_log.csv')})
 resources={(system,r['resource_id']) for _,_,_,system,r in main.evidence()}
 observed={}
 for eid,_,_,system,record in main.evidence():
  observed.setdefault((eid,system,record['resource_id']),set()).add(main.state(system,record))
 manifest={r['file_id']:r for r in main.read('evidence_files.csv')}
 record_by_key={}
 for eid,_,_,system,record in main.evidence():record_by_key.setdefault((eid,system,record['resource_id']),[]).append(record)
 resources.update((r['target_system'],r['resource_id']) for r in main.read('system_activity.csv'))
 resources.update((r['source_system'],r['resource_id']) for r in main.read('system_activity.csv'))
 for row in output:
  case=row['case_id'];status=row['deletion_status']
  if status not in ('COMPLETE','INCOMPLETE','NOT_APPLICABLE'):error(case,'invalid deletion_status')
  try:steps=json.loads(row['steps_json'])
  except (json.JSONDecodeError,TypeError):error(case,'steps_json is not valid JSON');continue
  if not isinstance(steps,list):error(case,'steps_json is not an array');continue
  if status=='NOT_APPLICABLE' and steps:error(case,'NOT_APPLICABLE must have []')
  if status=='COMPLETE' and not steps:error(case,'COMPLETE has no evidence-backed verification')
  if status=='INCOMPLETE' and not steps:error(case,'INCOMPLETE has no findings, remediation, or verification')
  phases=Counter();seen=set()
  for index,s in enumerate(steps,1):
   if not isinstance(s,dict):error(case,f'step {index} is not an object');continue
   if set(s)!=FIELDS:error(case,f'step {index} has wrong fields')
   if s.get('step_no')!=index:error(case,f'step {index} is misnumbered')
   op=s.get('operation')
   if op not in main.OPS:error(case,f'step {index} has unsupported operation');continue
   phase,state=main.OPS[op]
   if s.get('phase')!=phase or s.get('state')!=state:error(case,f'step {index} has wrong phase or state')
   phases[phase]+=1
   key=(op,s.get('system_id'),s.get('resource_id'))
   if key in seen:error(case,f'duplicate step {key}')
   seen.add(key)
   if (s.get('system_id'),s.get('resource_id')) not in resources:errors.append({'case_id':case,'message':f'unsupported resource {s.get("system_id")}/{s.get("resource_id")}'})
   eid=s.get('evidence_id')
   if eid:
    if eid not in known:error(case,f'unknown evidence {eid}')
    elif case in req and known[eid]>req[case]['audit_at']:error(case,f'evidence {eid} is after audit_at')
    if eid in manifest:
     states=observed.get((eid,s.get('system_id'),s.get('resource_id')),set())
     scoped_absence=(op=='VERIFY_RECORD_ABSENT' and s.get('system_id')=='account_service'
                     and 'customer_accounts_failover_replica' in manifest[eid]['file_path']
                     and s.get('resource_id') not in {rid for file_id,sys,rid in observed if file_id==eid and sys=='account_service'})
     if not states and not scoped_absence:error(case,f'step {index} citation does not contain the resource')
     required={'REPORT_REMAINING_RECORD':{'PRESENT','CONTACT_PRESENT','ATTACHMENT_PRESENT'},
               'REPORT_EXPOSED_PII':{'PRESENT'},'REPORT_ACTIVE_DATA_FLOW':{'ACTIVE'},
               'REPORT_RESTORE_RISK':{'ACTIVE'},'VERIFY_RECORD_ABSENT':{'ABSENT'},
               'VERIFY_RECORD_PRESENT':{'PRESENT'},'VERIFY_RECORD_REDACTED':{'REDACTED'},
               'VERIFY_RECORD_ANONYMIZED':{'ANONYMIZED'},'VERIFY_DATA_FLOW_DISABLED':{'DISABLED'},
               'VERIFY_RESTORE_BLOCKED':{'BLOCKED'}}.get(op)
     if states and required and not (states&required):error(case,f'step {index} citation does not prove {op}')
     if case in req and states:
      uid=next(iter(sorted(reverse.get(req[case]['email'].casefold(),()))),None)
      subject_keys=set(ids_by_user.get(uid,()))|{req[case]['email'].casefold()}
      is_catalog_linked=any(sys==s.get('system_id') and rid==s.get('resource_id') and at<=req[case]['audit_at'] and subjects&subject_keys
                            for at,sys,rid,_,subjects in main.catalog_links())
      if is_catalog_linked:
       if visible_identity_conflict(record_by_key.get((eid,s.get('system_id'),s.get('resource_id')),[]),subject_keys):
        warnings.append({'case_id':case,'message':f'step {index} catalog identity conflicts with earlier visible email on {s.get("resource_id")}'})
   elif phase=='FINDING' or status=='COMPLETE':error(case,f'step {index} lacks required evidence')
   if status=='INCOMPLETE' and phase!='FINDING' and eid:error(case,f'future step {index} has evidence')
   if status=='COMPLETE' and phase!='VERIFICATION':error(case,'COMPLETE contains non-verification step')
  if status=='INCOMPLETE' and steps:
   for phase in ('FINDING','REMEDIATION','VERIFICATION'):
    if phases[phase]==0:error(case,f'INCOMPLETE lacks {phase} phase')
  if all(isinstance(s,dict) and s.get('operation') in main.OPS for s in steps):
   ordered=sorted(steps,key=lambda s:(main.PHASE[s['phase']],main.ORDER[s['operation']],s['system_id'],s['resource_id']))
   if steps!=ordered:error(case,'steps are not in required order')
 report={'passed':not errors,'request_count':len(requests),'output_count':len(output),'error_count':len(errors),'warning_count':len(warnings),'errors':errors,'warnings':warnings}
 target=ROOT/'evaluation'/'validation_report.json';target.parent.mkdir(exist_ok=True)
 target.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 return report

if __name__=='__main__':
 report=validate();print(f"validation: {'PASS' if report['passed'] else 'FAIL'}; {report['error_count']} errors")
 for item in report['errors'][:20]:print(item['case_id'],item['message'])
 sys.exit(0 if report['passed'] else 1)
