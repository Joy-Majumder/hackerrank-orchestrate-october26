"""Deterministic participant-evidence deletion auditor."""
import csv, json, re, sqlite3, zlib, base64
from datetime import datetime
from functools import lru_cache
import os, shutil, subprocess, tempfile
from pathlib import Path
from collections import defaultdict

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'dataset'
OPS={'REPORT_REMAINING_RECORD':('FINDING','PRESENT'),'REPORT_EXPOSED_PII':('FINDING','PRESENT'),'REPORT_ACTIVE_DATA_FLOW':('FINDING','ACTIVE'),'REPORT_RESTORE_RISK':('FINDING','ACTIVE'),'DISABLE_DATA_FLOW':('REMEDIATION','DISABLED'),'BLOCK_RESTORE':('REMEDIATION','BLOCKED'),'DELETE_RECORD':('REMEDIATION','ABSENT'),'REDACT_RECORD':('REMEDIATION','REDACTED'),'ANONYMIZE_RECORD':('REMEDIATION','ANONYMIZED'),'VERIFY_RECORD_ABSENT':('VERIFICATION','ABSENT'),'VERIFY_RECORD_PRESENT':('VERIFICATION','PRESENT'),'VERIFY_RECORD_REDACTED':('VERIFICATION','REDACTED'),'VERIFY_RECORD_ANONYMIZED':('VERIFICATION','ANONYMIZED'),'VERIFY_DATA_FLOW_DISABLED':('VERIFICATION','DISABLED'),'VERIFY_RESTORE_BLOCKED':('VERIFICATION','BLOCKED')}
ORDER={op:i for i,op in enumerate(OPS)}
PHASE={'FINDING':0,'REMEDIATION':1,'VERIFICATION':2}
STATE_RISK={'ACTIVE':3,'PRESENT':3,'CONTACT_PRESENT':3,'ATTACHMENT_PRESENT':3,
            'REDACTED':1,'ANONYMIZED':1,'ABSENT':0,'DISABLED':0,'BLOCKED':0}

def read(name):
 with (DATA/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def tokens(v):
 if isinstance(v,dict):
  for x in v.values():yield from tokens(x)
 elif isinstance(v,list):
  for x in v:yield from tokens(x)
 elif v is not None:yield str(v).strip().casefold()

def system(rid):
 return {'account':'account_service','search':'search_service','analytics':'analytics_platform','support':'support_platform','export':'export_service','backup':'backup_service','audit':'security_service','data':'integration_service','tombstone':'identity_service','marketing':'marketing_platform','email':'notification_service','cache':'cache_service','object':'object_storage'}.get(rid.split('_')[0],'')

@lru_cache(maxsize=1)
def catalog_links():
 """Identity associations only; a separate artifact must prove resource state."""
 links=[]
 for row in activities():
  if row['event_type']!='LINK_RESOURCE_IDENTITY':continue
  details=row['details']
  alias=re.search(r'\(([^)]+)\)',details)
  subjects=set(x.casefold() for x in re.findall(r'[\w.+-]+@[\w.-]+|\buser_\d+\b',details))
  if subjects:
   links.append((row['event_time'],row['target_system'],row['resource_id'],alias.group(1) if alias else '',subjects))
 return links

def linked_category(sys):
 return {'export_service':'USER_EXPORT','object_storage':'SUPPORT_ATTACHMENT',
         'identity_service':'ACCOUNT_TOMBSTONE'}.get(sys,'')

def image_text(paths):
 """Use available local OCR; absence of OCR never invents image facts."""
 result=defaultdict(list)
 if not paths:return result
 try:
  from ocr_cache import IMAGE_TEXT
  if all(path.name in IMAGE_TEXT for path in paths):
   for path in paths:result[str(path)]=IMAGE_TEXT[path.name]
   return result
 except ImportError:pass
 if shutil.which('swift'):
  cache=Path(tempfile.gettempdir())/'ghost-data-swift-cache'
  cache.mkdir(exist_ok=True)
  try:
   p=subprocess.run(['swift','-module-cache-path',str(cache),str(ROOT/'code'/'ocr.swift'),*[str(x) for x in paths]],capture_output=True,text=True,timeout=180)
   if p.returncode==0:
    for line in p.stdout.splitlines():
     if '\t' in line:
      name,value=line.split('\t',1);result[name].append(value)
  except (OSError,subprocess.TimeoutExpired):pass
 if shutil.which('tesseract'):
  for path in paths:
   if result[str(path)]:continue
   try:
    p=subprocess.run(['tesseract',str(path),'stdout'],capture_output=True,text=True,timeout=30)
    if p.returncode==0:result[str(path)]=p.stdout.splitlines()
   except (OSError,subprocess.TimeoutExpired):pass
 if os.environ.get('WRITE_OCR_CACHE')=='1' and all(result.get(str(path)) for path in paths):
  (ROOT/'code'/'ocr_cache.py').write_text('"""OCR text extracted from the participant-facing evidence screenshots."""\nIMAGE_TEXT = '+repr({path.name:result[str(path)] for path in paths})+'\n',encoding='utf-8')
 return result

def identity():
 ids=defaultdict(set);reverse=defaultdict(set)
 for r in read('user_identities.csv'):
  ids[r['user_id']].update(v for v in tokens(r) if len(v)>6)
  ids[r['user_id']].add(r['user_id'])
 for r in read('user_audit_log.csv'):
  ids[r['user_id']].update(str(r[k]).strip().casefold() for k in ('old_value','new_value') if len(r[k])>6)
 for uid,vals in ids.items():
  for v in vals:reverse[v].add(uid)
 return ids,reverse

def evidence():
 found=[]
 manifest=read('evidence_files.csv')
 aliases=[(sys,rid,alias) for _,sys,rid,alias,_ in catalog_links() if alias and alias!=rid]
 images=image_text([DATA/m['file_path'] for m in manifest if m['file_path'].endswith('.png')])
 for m in manifest:
  p=DATA/m['file_path'];eid=m['file_id'];cap=m['captured_at']
  def add(rec,at,sys=''):
   rid=rec.get('resource_id','')
   if rid:found.append((eid,cap,at,sys or system(rid),rec))
  if p.suffix=='.json':
   d=json.loads(p.read_text(encoding='utf-8'))
   if 'snapshots' in d:
    for s in d['snapshots']:
     for r in s.get('records',[]):
      r=dict(r);r['_collection']=s.get('collection','');add(r,s['captured_at'],s['data_store'])
   elif 'service_exports' in d:
    for sys,groups in d['service_exports'].items():
     for rows in groups.values():
      for r in rows:
       r=dict(r);r['_collection']=next((k for k,v in groups.items() if v is rows),'');add(r,r.get('observed_at',cap),sys)
   elif 'records' in d:
    for r in d['records']:add(r,r.get('recorded_at',cap),r.get('system',''))
   else:
    for group in d.values():
     if isinstance(group,list):
      for r in group:
       if isinstance(r,dict):add(r,r.get('observed_at',cap),r.get('system',''))
  elif p.suffix=='.sql':
   db=sqlite3.connect(':memory:')
   try:
    db.executescript(p.read_text(encoding='utf-8'))
    scope={}
    try:scope=dict(db.execute('select origin_system,captured_at from snapshot_scope'))
    except sqlite3.Error:pass
    for (table,) in db.execute("select name from sqlite_master where type='table'"):
     if table=='snapshot_scope':continue
     cur=db.execute('select * from "'+table+'"');names=[x[0] for x in cur.description]
     for row in cur:
      r=dict(zip(names,row))
      if r.get('record_json'):
       try:r={**r,**json.loads(r['record_json'])}
       except json.JSONDecodeError:pass
      r['_collection']=r.get('collection_name',table)
      add(r,scope.get(r.get('origin_system') or system(r.get('resource_id','')),cap),r.get('origin_system',''))
   finally:db.close()
  elif p.suffix=='.pdf':
   blob=p.read_bytes()
   for stream in re.finditer(rb'stream\r?\n(.*?)endstream',blob,re.S):
    raw=stream.group(1).strip()
    try:
     decoded=zlib.decompress(base64.a85decode(raw,adobe=True)) if raw.endswith(b'~>') else zlib.decompress(raw)
    except Exception:continue
    if b'Tj' not in decoded:continue
    text=' '.join(x.decode('latin-1') for x in re.findall(rb'\(([^()]*)\)\s*Tj',decoded))
    for rid in set(re.findall(r'\b(?:account|support|audit_record|analytics|backup|export|search)_\d+\b',text)):
     add({'resource_id':rid,'document_text':text,'pdf_attachment':p.name=='delivery_correction_attachment.pdf'},cap)
    for link_sys,rid,alias in aliases:
     if alias in text:
      record={'resource_id':rid,'document_text':text}
      if linked_category(link_sys):record['record_type']=linked_category(link_sys)
      add(record,cap,link_sys)
  elif p.suffix=='.png':
   lines=images.get(str(p),[])
   for n,line in enumerate(lines):
    for rid in set(re.findall(r'\b(?:account|support|audit_record|analytics|backup|export|search|marketing|tombstone|data_flow|object)_\d+\b',line)):
     nearby=' '.join(lines[max(0,n-8):min(len(lines),n+9)])
     add({'resource_id':rid,'image_text':nearby,'raw_line':nearby},cap)
   image_blob=' '.join(lines)
   for link_sys,rid,alias in aliases:
    if alias in image_blob:
     record={'resource_id':rid,'image_text':image_blob}
     if linked_category(link_sys):record['record_type']=linked_category(link_sys)
     add(record,cap,link_sys)
  elif p.suffix in ('.log','.txt'):
   lines=p.read_text(encoding='utf-8',errors='replace').splitlines()
   traces=defaultdict(list)
   for line in lines:
    mtrace=re.search(r'\b(?:tr|rb)-[A-Za-z0-9-]+\b',line)
    if mtrace:traces[mtrace.group(0)].append(line)
   for line in lines:
    if p.suffix=='.txt' and ' | ' in line:
     parts=[x.strip() for x in line.lstrip('- ').split('|')]
     if len(parts)>=6 and re.match(r'20\d\d-',parts[0]):
      add({'resource_id':parts[2],'record_type':parts[3],'result':parts[4],'subject_reference':parts[5],'raw_line':line},parts[0],parts[1]);continue
    match=re.search(r'\bresource_id\\?["\']?\s*[:=]\s*\\?["\']?([\w-]+)',line)
    if match:
     if re.search(r'\bevent=[\w]+_started\b',line):continue
     mtrace=re.search(r'\b(?:tr|rb)-[A-Za-z0-9-]+\b',line)
     context=' '.join(traces[mtrace.group(0)]) if mtrace else line
     add({'resource_id':match.group(1),'raw_line':line,'trace_context':context},line[:20] if re.match(r'20\d\d-',line) else cap)
 return found

def state(sys,r):
 raw=r.get('raw_line','').casefold().replace('\\"','"')
 if 'status_code' in r:return 'ABSENT' if r['status_code']==404 or r.get('profile') is None else 'PRESENT'
 if 'hits' in r:return 'ABSENT' if r['hits'].get('total',0)==0 else 'PRESENT'
 if 'result' in r:
  return {'NOT_FOUND':'ABSENT','ABSENT':'ABSENT','ANONYMIZED':'ANONYMIZED','REDACTED':'REDACTED','DISABLED':'DISABLED','BLOCKED':'BLOCKED','ACTIVE':'ACTIVE','IDENTIFIABLE':'PRESENT'}.get(r['result'],'PRESENT')
 if raw:
  def value(key,val):return bool(re.search(r'\b'+re.escape(key)+r'\s*"?\s*[:=]\s*"?'+re.escape(val)+r'\b',raw))
  if any(value(k,v) for k,v in (('result','miss'),('rows','0'),('http_status','404'),('result','not_found'))):return 'ABSENT'
  if sys=='support_platform' and 'support_replica' in raw and (value('rows','1') or value('marker_found','false')):return 'CONTACT_PRESENT'
  if sys=='support_platform' and 'message_pii_scan' in raw and 'matched_value=' in raw:return 'PRESENT'
  if any(value('enabled',v) for v in ('false','0')):return 'DISABLED'
  if any(value('restore_allowed',v) for v in ('false','0')) or value('deletion_block','true'):return 'BLOCKED'
  if any(value('enabled',v) for v in ('true','1')):return 'ACTIVE'
  if any(value('restore_allowed',v) for v in ('true','1')) or value('deletion_block','false'):return 'ACTIVE'
  if sys=='analytics_platform' and 'contact_lookup_completed' in raw and value('rows','1'):return 'CONTACT_PRESENT'
  if sys=='analytics_platform' and ('email=' in raw or 'email_hash=' in raw or 'direct_identifiers=' in raw):
   return 'ANONYMIZED' if value('direct_identifiers','0') or (value('email','null') and value('email_hash','null')) else 'PRESENT'
  if sys=='support_platform' and 'requester_email=' in raw:return 'REDACTED' if value('requester_email','null') else 'PRESENT'
 if sys=='integration_service':return 'ACTIVE' if r.get('enabled') in (1,True,'1') else 'DISABLED'
 if sys=='backup_service':return 'ACTIVE' if r.get('restore_allowed') in (1,True,'1') else 'BLOCKED'
 if sys=='analytics_platform':return 'PRESENT' if any(r.get(k) for k in ('user_id','customer_reference','email','phone','email_hash')) else 'ANONYMIZED'
 if r.get('pdf_attachment'):return 'ATTACHMENT_PRESENT'
 if sys in ('support_platform','identity_service','notification_service'):
  direct=any(r.get(k) for k in ('name','full_name','email','phone','email_hash','requester_name','requester_email','requester_phone','customer_email'))
  message=' '.join(str(r.get(k) or '') for k in ('message_text','message_excerpt','body'))
  embedded=bool(re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',message))
  return 'PRESENT' if direct or embedded else 'REDACTED'
 return 'PRESENT'

def request_deletion(t):
 t=t.casefold()
 if any(s in t for s in ("do not delete","don't delete","do not close","don't close","not asking for deletion","not requesting deletion","not a request to erase","without deleting","without removing","no deletion")):return False
 if re.search(r'\b(?:remove|unsubscribe|opt out)\b.*\b(?:marketing|promotional)\b.*\bonly\b',t):return False
 return any(re.search(p,t) for p in (r'\bdelet',r'\beras',r'\bremov',r'\bclos(?:e|ed|ing)',r'\bforget me',r'\bgo(?:ne)?\b',r'\bsupprim',r'\bsuppres',r'\beffac',r'\belimin',r'\bborrar',r'\blösch',r'\bcancellazione',r'\bexclu',r'削除',r'删除',r'삭제',r'حذف'))

def policy_actions():
 """Load participant policy; conditional rules are interpreted per record below."""
 return {r['data_category']:r['required_action'] for r in read('deletion_rules.csv')}

@lru_cache(maxsize=1)
def activities():return read('system_activity.csv')

def nearby_account(req):
 """Link a uniquely timed account deletion claim to a resource, never to its state."""
 def dt(value):return datetime.fromisoformat(value.replace('Z','+00:00'))
 reported=dt(req['reported_at'])
 candidates=sorted((abs((dt(a['event_time'])-reported).total_seconds()),a['resource_id']) for a in activities()
                   if a['event_type']=='DELETE_RECORD' and a['target_system']=='account_service'
                   and req['requested_at']<=a['event_time']<=req['audit_at'])
 if candidates and candidates[0][0]<=600 and (len(candidates)==1 or candidates[1][0]>1800):return candidates[0][1]
 return None

def nearby_anonymized_profile(req,ev):
 """A unique nearby operation locates an ID; a later snapshot proves its state."""
 def dt(value):return datetime.fromisoformat(value.replace('Z','+00:00'))
 reported=dt(req['reported_at'])
 candidates=sorted((abs((dt(a['event_time'])-reported).total_seconds()),a['resource_id']) for a in activities()
                   if a['event_type']=='ANONYMIZE_RECORD' and a['target_system']=='analytics_platform'
                   and req['requested_at']<=a['event_time']<=req['audit_at'])
 if not candidates or candidates[0][0]>600 or (len(candidates)>1 and candidates[1][0]<=1800):return None
 rid=candidates[0][1]
 observations=[(at,cap,eid,sys,r) for eid,cap,at,sys,r in ev if sys=='analytics_platform'
               and r.get('resource_id')==rid and cap<=req['audit_at'] and at<=req['audit_at']]
 if not observations:return None
 at,cap,eid,sys,r=max(observations,key=lambda item:item[:2])
 if state(sys,r)!='ANONYMIZED':return None
 return (sys,rid),(at,cap,eid,'ANONYMIZED',category(sys,r,'ANONYMIZED'))

def absent_account_evidence(req,rid,ev):
 """A full account primary/failover snapshot can establish that a linked ID is absent."""
 manifest=[m for m in read('evidence_files.csv') if 'customer_accounts_failover_replica' in m['file_path']
           and req['reported_at']<=m['captured_at']<=req['audit_at']]
 for m in sorted(manifest,key=lambda x:x['captured_at'],reverse=True):
  if not any(eid==m['file_id'] and rec.get('resource_id')==rid for eid,_,_,_,rec in ev):return m['file_id']
 return ''

def category(sys,r,current):
 explicit=r.get('record_type') or r.get('data_category')
 if explicit:return explicit
 collection=r.get('_collection','').lower()
 if r.get('pdf_attachment'):return 'SUPPORT_ATTACHMENT'
 if current=='CONTACT_PRESENT':return 'SECONDARY_IDENTIFIER'
 if sys=='account_service':return 'USER_PROFILE'
 if sys=='search_service':return 'SEARCH_INDEX_ENTRY'
 if sys=='analytics_platform':return 'ANALYTICS_PROFILE'
 if sys=='support_platform':return 'SUPPORT_MESSAGE'
 if sys=='security_service':return 'SECURITY_AUDIT_LOG'
 if sys=='backup_service':return 'BACKUP_ARCHIVE'
 if sys=='integration_service':return 'DATA_FLOW'
 if sys=='identity_service':return 'ACCOUNT_TOMBSTONE'
 if sys=='notification_service':return 'EMAIL_DELIVERY_LOG'
 if sys=='export_service':return 'USER_EXPORT'
 if sys in ('marketing_service','marketing_platform'):return 'MARKETING_PROFILE'
 if sys=='cache_service':return 'CACHE_ENTRY'
 if sys=='object_storage':return 'SUPPORT_ATTACHMENT'
 return 'USER_PROFILE'

def step(op,sys,rid,eid=''):
 phase,value=OPS[op]
 return dict(step_no=0,phase=phase,system_id=sys,resource_id=rid,operation=op,state=value,evidence_id=eid)

def matches_subject(record,keys):
 vals=set(tokens(record));blob=' '.join(vals)
 return any(k in vals or (len(k)>12 and k in blob) or
            (k.startswith('user_') and re.search(r'(?<![\w])'+re.escape(k)+r'(?![\w])',blob)) for k in keys)

def audit(req,ids,reverse,ev):
 if not request_deletion(req['request_text']):return 'NOT_APPLICABLE',[]
 uid=next(iter(sorted(reverse.get(req['email'].casefold(),()))),None)
 keys=set(ids.get(uid,()))|{req['email'].casefold()};keys={k for k in keys if len(k)>6}
 linked_resources={(sys,rid) for at,sys,rid,_,subjects in catalog_links()
                   if req['requested_at']<=at<=req['audit_at'] and keys&subjects}
 # Earlier identity-bearing records can link a resource to a later compliant
 # observation, but an old snapshot alone cannot prove its state at audit_at.
 linked_resources.update((sys,r['resource_id']) for _,cap,at,sys,r in ev
                         if cap<=req['audit_at'] and at<req['requested_at'] and sys
                         and matches_subject(r,keys))
 latest={}
 for eid,cap,at,sys,r in ev:
  if cap>req['audit_at'] or at>req['audit_at'] or at<req['requested_at'] or not sys:continue
  owner=str(r.get('user_id') or r.get('subject_reference') or '').casefold()
  if re.fullmatch(r'user_\d+',owner) and owner not in keys:continue
  if (sys,r['resource_id']) not in linked_resources and not matches_subject(r,keys):continue
  key=(sys,r['resource_id']);v=(at,cap,eid,state(sys,r),category(sys,r,state(sys,r)))
  # Replicas at the same observation time can disagree; preserve the exposed
  # copy until a strictly later eligible observation establishes its treatment.
  if key not in latest or (v[:2],STATE_RISK.get(v[3],0))>=(latest[key][:2],STATE_RISK.get(latest[key][3],0)):
   latest[key]=v
 linked=nearby_account(req) if not any(sys=='account_service' for sys,_ in latest) else None
 if linked:
  proof=absent_account_evidence(req,linked,ev)
  if proof:latest[('account_service',linked)]=(req['reported_at'],req['reported_at'],proof,'ABSENT','USER_PROFILE')
 nearby_analytics=nearby_anonymized_profile(req,ev)
 if nearby_analytics and nearby_analytics[0] not in latest:latest[nearby_analytics[0]]=nearby_analytics[1]
 findings=[];remedies=[];checks=[]
 actions=policy_actions()
 for (sys,rid),(_,_,eid,current,cat) in latest.items():
  if sys=='integration_service':
   if current=='ACTIVE':findings.append(step('REPORT_ACTIVE_DATA_FLOW',sys,rid,eid));remedies.append(step('DISABLE_DATA_FLOW',sys,rid))
   checks.append(step('VERIFY_DATA_FLOW_DISABLED',sys,rid,eid if current!='ACTIVE' else ''))
  elif sys=='backup_service':
   if current=='ACTIVE':findings.append(step('REPORT_RESTORE_RISK',sys,rid,eid));remedies.append(step('BLOCK_RESTORE',sys,rid))
   checks.append(step('VERIFY_RESTORE_BLOCKED',sys,rid,eid if current!='ACTIVE' else ''))
  elif actions.get(cat)=='RETAIN' and sys=='security_service':checks.append(step('VERIFY_RECORD_PRESENT',sys,rid,eid))
  else:
   action=actions.get(cat,'DELETE')
   desired={'DELETE':'ABSENT','REDACT':'REDACTED','ANONYMIZE':'ANONYMIZED','RETAIN':'PRESENT'}.get(action,'ABSENT')
   if current=='ATTACHMENT_PRESENT':desired='ABSENT'
   if current=='CONTACT_PRESENT':desired='ABSENT'
   if desired=='PRESENT':
    if current=='PRESENT':checks.append(step('VERIFY_RECORD_PRESENT',sys,rid,eid))
    continue
   verify={'ABSENT':'VERIFY_RECORD_ABSENT','REDACTED':'VERIFY_RECORD_REDACTED','ANONYMIZED':'VERIFY_RECORD_ANONYMIZED'}[desired]
   if current!=desired:
    findings.append(step('REPORT_REMAINING_RECORD' if desired=='ABSENT' else 'REPORT_EXPOSED_PII',sys,rid,eid))
    remedies.append(step({'ABSENT':'DELETE_RECORD','REDACTED':'REDACT_RECORD','ANONYMIZED':'ANONYMIZE_RECORD'}[desired],sys,rid))
   checks.append(step(verify,sys,rid,eid if current==desired else ''))
 status='INCOMPLETE' if findings else 'COMPLETE'
 if linked and status=='INCOMPLETE' and not any(s['resource_id']==linked for s in checks):
  checks.append(step('VERIFY_RECORD_ABSENT','account_service',linked))
 if findings:
  for s in checks:s['evidence_id']=''
 steps=(findings+remedies+checks) if findings else checks
 steps.sort(key=lambda s:(PHASE[s['phase']],ORDER[s['operation']],s['system_id'],s['resource_id']))
 for n,s in enumerate(steps,1):s['step_no']=n
 return status,steps

def main():
 ids,reverse=identity();ev=evidence();requests=read('deletion_requests.csv')
 with (ROOT/'output.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.writer(f,lineterminator='\n');w.writerow(('case_id','deletion_status','steps_json'))
  for r in sorted(requests,key=lambda r:r['case_id']):
   status,steps=audit(r,ids,reverse,ev);w.writerow((r['case_id'],status,json.dumps(steps,ensure_ascii=False,separators=(',',':'))))
 print('Wrote',len(requests),'cases')

if __name__=='__main__':main()
