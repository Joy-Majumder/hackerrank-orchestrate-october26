"""Independent synthetic edge cases for the participant audit engine."""
import sys
import unittest
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

if __name__=='__main__':unittest.main()
