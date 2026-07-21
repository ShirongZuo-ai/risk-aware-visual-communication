import json,tempfile,unittest
from pathlib import Path
from scripts.m6a_v2_runtime_evidence import *
class T(unittest.TestCase):
 def test_actual_files_reload_and_tamper_fail(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);i={'launch_id':'l','attempt_id':'a','identity_id':'e','scene_id':'S1','seed':1}
   files={}
   for n in ('summary','status','diagnostic','snapshot0','snapshot1','snapshot2','snapshot3'):
    p=r/(n+'.json');p.write_text(json.dumps({'n':n}));files[n]=p
   m=persist_runtime_manifest(r/'runtime_artifacts.json',i,r,files);self.assertEqual(load_runtime_manifest(r/'runtime_artifacts.json',i,r)['sha256'],m['sha256'])
   files['summary'].write_text('{}')
   with self.assertRaises(ValueError):load_runtime_manifest(r/'runtime_artifacts.json',i,r)
 def test_validation_and_joint_reloadable(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);i={'launch_id':'l','attempt_id':'a','identity_id':'e','scene_id':'S1','seed':1};src=r/'aggregate.json';src.write_text('{}');v=persist_validation(r/'aggregate_validation.json','m6a-v2-aggregate-validation-v1',i,src,True);self.assertEqual(load_validation(r/'aggregate_validation.json','m6a-v2-aggregate-validation-v1',i)['sha256'],v['sha256']);j=persist_joint_report(r/'joint.json',i,{'aggregate':r/'aggregate_validation.json'});self.assertTrue(j['passed'])
 def test_process_evidence_reloads_actual_streams(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);i={'launch_id':'l','attempt_id':'a','identity_id':'e','scene_id':'S1','seed':1};(r/'out').write_bytes(b'o');(r/'err').write_bytes(b'e');persist_process_evidence(r/'process.json',i,r/'out',r/'err',started_at_utc='2026-01-01T00:00:00Z',ended_at_utc='2026-01-01T00:00:01Z',return_code=0,timeout_state=False,termination_state=False,backend_identity='fake',launch_performed=True,webots_started=False);self.assertEqual(load_process_evidence(r/'process.json',i)['return_code'],0);(r/'out').write_bytes(b'x')
   with self.assertRaises(ValueError):load_process_evidence(r/'process.json',i)
