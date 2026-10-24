"""Independent synthetic edge cases for the participant audit engine."""
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import main

T0='2020-01-01T00:00:00Z'
T1='2020-01-02T00:00:00Z'
T2='2020-01-03T00:00:00Z'
USER='user_custom'
OLD='old@example.test'
IDS={USER:{USER,OLD,'new@example.test'}}
REVERSE={OLD:{USER}}

def request(text='Please delete my account and personal data.'):
 return dict(case_id='custom',email=OLD,requested_at=T0,reported_at=T1,audit_at=T2,request_text=text)

def observation(system,resource,record,at=T1):
 return ('evidence_custom',at,at,system,{'resource_id':resource,**record})

class AuditEdgeCases(unittest.TestCase):
 def test_historical_email_remaining_in_search(self):
  ev=[observation('search_service','search_123',{'email':OLD})]
  status,steps=main.audit(request(),IDS,REVERSE,ev)
  self.assertEqual(status,'INCOMPLETE')
  self.assertEqual([s['operation'] for s in steps],['REPORT_REMAINING_RECORD','DELETE_RECORD','VERIFY_RECORD_ABSENT'])
  self.assertEqual(steps[0]['evidence_id'],'evidence_custom')

 def test_active_sync_is_disabled_before_record_change(self):
  ev=[observation('integration_service','data_flow_123',{'customer_email':OLD,'enabled':True}),
      observation('search_service','search_123',{'email':OLD})]
  status,steps=main.audit(request(),IDS,REVERSE,ev)
  self.assertEqual(status,'INCOMPLETE')
  self.assertEqual([s['operation'] for s in steps],['REPORT_REMAINING_RECORD','REPORT_ACTIVE_DATA_FLOW','DISABLE_DATA_FLOW','DELETE_RECORD','VERIFY_RECORD_ABSENT','VERIFY_DATA_FLOW_DISABLED'])

 def test_retained_support_message_redacts_pii(self):
  ev=[observation('support_platform','support_123',{'record_type':'SUPPORT_MESSAGE','customer_reference':USER,'requester_email':OLD,'message_text':'Order context retained.'})]
  status,steps=main.audit(request(),IDS,REVERSE,ev)
  self.assertEqual(status,'INCOMPLETE')
  self.assertEqual([s['operation'] for s in steps],['REPORT_EXPOSED_PII','REDACT_RECORD','VERIFY_RECORD_REDACTED'])

 def test_tombstone_keeps_stable_reference_and_redacts_email(self):
  exposed=[observation('identity_service','tombstone_123',{'record_type':'ACCOUNT_TOMBSTONE','user_id':USER,'email':OLD})]
  status,steps=main.audit(request(),IDS,REVERSE,exposed)
  self.assertEqual(status,'INCOMPLETE')
  self.assertEqual(steps[1]['operation'],'REDACT_RECORD')
  compliant=[observation('identity_service','tombstone_123',{'record_type':'ACCOUNT_TOMBSTONE','user_id':USER})]
  status,steps=main.audit(request(),IDS,REVERSE,compliant)
  self.assertEqual(status,'COMPLETE')
  self.assertEqual([s['operation'] for s in steps],['VERIFY_RECORD_REDACTED'])

 def test_restore_risk_is_blocked(self):
  ev=[observation('backup_service','backup_123',{'customer_email':OLD,'restore_allowed':True})]
  status,steps=main.audit(request(),IDS,REVERSE,ev)
  self.assertEqual(status,'INCOMPLETE')
  self.assertEqual([s['operation'] for s in steps],['REPORT_RESTORE_RISK','BLOCK_RESTORE','VERIFY_RESTORE_BLOCKED'])

 def test_non_deletion_intents(self):
  for text in ('Do not close the account; reset my login.',
               'Correct my surname without removing records.',
               'Please remove me from marketing lists only.',
               'This is an information request, not a request to erase it.'):
   with self.subTest(text=text):
    self.assertEqual(main.audit(request(text),IDS,REVERSE,[]),('NOT_APPLICABLE',[]))

 def test_catalog_link_connects_identifier_free_export(self):
  ev=[observation('export_service','export_222',{'record_type':'USER_EXPORT','document_text':'Export ready'})]
  links=[(T1,'export_service','export_222','statement-222',{USER,OLD})]
  with patch.object(main,'catalog_links',return_value=links):
   status,steps=main.audit(request(),IDS,REVERSE,ev)
  self.assertEqual(status,'INCOMPLETE')
  self.assertEqual([s['operation'] for s in steps],['REPORT_REMAINING_RECORD','DELETE_RECORD','VERIFY_RECORD_ABSENT'])
  self.assertEqual(steps[0]['evidence_id'],'evidence_custom')

 def test_catalog_link_proves_identity_but_snapshot_proves_absence(self):
  ev=[observation('account_service','account_222',{'status_code':404,'profile':None})]
  links=[(T1,'account_service','account_222','account_222',{USER,OLD})]
  with patch.object(main,'catalog_links',return_value=links):
   status,steps=main.audit(request(),IDS,REVERSE,ev)
  self.assertEqual((status,[s['operation'] for s in steps]),('COMPLETE',['VERIFY_RECORD_ABSENT']))
  self.assertEqual(steps[0]['evidence_id'],'evidence_custom')

 def test_catalog_link_after_cutoff_is_ignored(self):
  ev=[observation('export_service','export_222',{'record_type':'USER_EXPORT','document_text':'Export ready'})]
  ev.append(observation('search_service','search_123',{'email':OLD}))
  links=[('2020-01-04T00:00:00Z','export_service','export_222','statement-222',{USER,OLD})]
  with patch.object(main,'catalog_links',return_value=links):
   status,steps=main.audit(request(),IDS,REVERSE,ev)
  self.assertEqual(status,'INCOMPLETE')
  self.assertEqual({s['resource_id'] for s in steps},{'search_123'})

 def test_later_snapshot_overrides_earlier_presence(self):
  ev=[observation('account_service','account_222',{'email':OLD},T1),
      observation('account_service','account_222',{'status_code':404,'profile':None,'email':OLD},'2020-01-02T01:00:00Z')]
  status,steps=main.audit(request(),IDS,REVERSE,ev)
  self.assertEqual((status,[s['operation'] for s in steps]),('COMPLETE',['VERIFY_RECORD_ABSENT']))

 def test_successful_activity_claim_does_not_override_present_snapshot(self):
  ev=[observation('search_service','search_123',{'email':OLD})]
  claim={'activity_id':'activity_synthetic','event_time':T1,'event_type':'DELETE_RECORD',
         'source_system':'deletion_worker','target_system':'search_service','resource_id':'search_123',
         'reported_result':'SUCCESS','details':'Deletion worker reported success.'}
  with patch.object(main,'activities',return_value=[claim]):
   status,steps=main.audit(request(),IDS,REVERSE,ev)
  self.assertEqual(status,'INCOMPLETE')
  self.assertEqual(steps[0]['operation'],'REPORT_REMAINING_RECORD')

 def test_post_audit_snapshot_cannot_override_remaining_record(self):
  ev=[observation('account_service','account_222',{'email':OLD},T1),
      observation('account_service','account_222',{'status_code':404,'profile':None,'email':OLD},'2020-01-04T00:00:00Z')]
  status,steps=main.audit(request(),IDS,REVERSE,ev)
  self.assertEqual(status,'INCOMPLETE')
  self.assertEqual(steps[0]['operation'],'REPORT_REMAINING_RECORD')

 def test_pre_request_identity_links_later_anonymized_snapshot(self):
  ev=[observation('analytics_platform','analytics_222',{'user_id':USER,'email':OLD},'2019-12-31T23:00:00Z'),
      observation('analytics_platform','analytics_222',{'user_id':None,'email':None,'phone':None,'email_hash':None},T1)]
  status,steps=main.audit(request(),IDS,REVERSE,ev)
  self.assertEqual((status,[s['operation'] for s in steps]),('COMPLETE',['VERIFY_RECORD_ANONYMIZED']))
  self.assertEqual(steps[0]['evidence_id'],'evidence_custom')

 def test_later_different_stable_owner_blocks_historical_link(self):
  ev=[observation('analytics_platform','analytics_222',{'user_id':USER,'email':OLD},'2019-12-31T23:00:00Z'),
      observation('analytics_platform','analytics_222',{'user_id':'user_999','email':'other@example.test'},T1),
      observation('search_service','search_123',{'email':OLD},T1)]
  status,steps=main.audit(request(),IDS,REVERSE,ev)
  self.assertEqual(status,'INCOMPLETE')
  self.assertEqual({s['resource_id'] for s in steps},{'search_123'})

 def test_same_time_replica_drift_preserves_exposed_copy(self):
  present=observation('account_service','account_222',{'email':OLD,'_collection':'primary'},T1)
  absent=observation('account_service','account_222',{'email':OLD,'status_code':404,'profile':None,'_collection':'failover'},T1)
  for evidence in ([present,absent],[absent,present]):
   with self.subTest(order=evidence[0][4]['_collection']):
    status,steps=main.audit(request(),IDS,REVERSE,evidence)
    self.assertEqual(status,'INCOMPLETE')
    self.assertEqual(steps[0]['operation'],'REPORT_REMAINING_RECORD')

 def test_retained_security_record_is_verified_present(self):
  ev=[observation('security_service','audit_record_222',{'record_type':'SECURITY_AUDIT_LOG','subject_reference':USER})]
  status,steps=main.audit(request(),IDS,REVERSE,ev)
  self.assertEqual((status,[s['operation'] for s in steps]),('COMPLETE',['VERIFY_RECORD_PRESENT']))

 def test_flow_and_restore_are_remediated_before_copy(self):
  ev=[observation('integration_service','data_flow_123',{'customer_email':OLD,'enabled':True}),
      observation('backup_service','backup_123',{'customer_email':OLD,'restore_allowed':True}),
      observation('search_service','search_123',{'email':OLD})]
  status,steps=main.audit(request(),IDS,REVERSE,ev)
  self.assertEqual(status,'INCOMPLETE')
  remedies=[s['operation'] for s in steps if s['phase']=='REMEDIATION']
  self.assertEqual(remedies,['DISABLE_DATA_FLOW','BLOCK_RESTORE','DELETE_RECORD'])

 def test_four_contract_failures_have_artifact_grounded_findings(self):
  ids,reverse=main.identity();ev=main.evidence()
  requests={r['case_id']:r for r in main.read('deletion_requests.csv')}
  proofs={'case_33':'evidence_18','case_52':'evidence_23','case_61':'evidence_46','case_63':'evidence_60'}
  for case,evidence_id in proofs.items():
   with self.subTest(case=case):
    status,steps=main.audit(requests[case],ids,reverse,ev)
    self.assertEqual(status,'INCOMPLETE')
    self.assertTrue(any(s['phase']=='FINDING' and s['evidence_id']==evidence_id for s in steps))

 def test_catalog_alias_preserves_tombstone_policy(self):
  self.assertEqual(main.linked_category('identity_service'),'ACCOUNT_TOMBSTONE')
  ids,reverse=main.identity();ev=main.evidence()
  case=next(r for r in main.read('deletion_requests.csv') if r['case_id']=='case_46')
  status,steps=main.audit(case,ids,reverse,ev)
  self.assertEqual(status,'COMPLETE')
  self.assertTrue(any(s['operation']=='VERIFY_RECORD_REDACTED' and s['resource_id']=='tombstone_17' for s in steps))

if __name__=='__main__':unittest.main()
