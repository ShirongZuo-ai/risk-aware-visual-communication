import json,tempfile,unittest
from dataclasses import replace
from pathlib import Path
from navigation.trajectory_prediction import CommandSegment
from scripts.m6a_common import VERSION
from scripts.m6a_dual_roi import CurrentState,ScheduleEvidence,SnapshotInput,process_m6a_snapshot,serialize_snapshot,load_and_validate_serialized_snapshot
from scripts.m6a_trusted_artifacts import M6AProjectionConfig

class TrustedSnapshotSerializationTests(unittest.TestCase):
 def setUp(self):
  state=CurrentState(0,0,0,.1,0);schedule=ScheduleEvidence('p',0,(CommandSegment(0,2,1,1),))
  self.manifest='manifest';self.output=process_m6a_snapshot(SnapshotInput(VERSION,self.manifest,'S1','episode',1,'0',0,state,'frame.png',schedule),M6AProjectionConfig())
 def write(self,root,name='snapshot'):return Path(root)/name
 def test_round_trip_and_exact_schema(self):
  with tempfile.TemporaryDirectory() as root:
   target=self.write(root);serialize_snapshot(self.output,target,manifest_hash=self.manifest,protocol_version=VERSION)
   self.assertEqual({p.name for p in target.iterdir()},{'snapshot_metadata.json','comparison.json','frame_reference.json','state_only_risk_roi','command_conditioned_risk_roi'})
   loaded=load_and_validate_serialized_snapshot(target,self.manifest);self.assertEqual(set(loaded.methods),{'state_only_risk_roi','command_conditioned_risk_roi'})
 def test_rejects_nonproduction_and_unsafe_output_before_write(self):
  with tempfile.TemporaryDirectory() as root:
   target=self.write(root)
   with self.assertRaises(ValueError):serialize_snapshot({},target,manifest_hash=self.manifest,protocol_version=VERSION)
   unsafe=replace(self.output,state_only_risk_roi=replace(self.output.state_only_risk_roi,synthetic_test_only=True))
   with self.assertRaises(ValueError):serialize_snapshot(unsafe,target,manifest_hash=self.manifest,protocol_version=VERSION)
   self.assertFalse(target.exists())
 def test_manifest_overwrite_and_nonempty_rejected(self):
  with tempfile.TemporaryDirectory() as root:
   target=self.write(root);serialize_snapshot(self.output,target,manifest_hash=self.manifest,protocol_version=VERSION)
   with self.assertRaises(FileExistsError):serialize_snapshot(self.output,target,manifest_hash=self.manifest,protocol_version=VERSION)
   with self.assertRaises(ValueError):serialize_snapshot(self.output,self.write(root,'m5_frozen'),manifest_hash=self.manifest,protocol_version=VERSION)
   with self.assertRaises(ValueError):serialize_snapshot(self.output,self.write(root,'bad'),manifest_hash='wrong',protocol_version=VERSION)
 def test_tampering_and_unknown_content_detected(self):
  with tempfile.TemporaryDirectory() as root:
   target=self.write(root);serialize_snapshot(self.output,target,manifest_hash=self.manifest,protocol_version=VERSION)
   path=target/'state_only_risk_roi'/'trajectory.json';data=json.loads(path.read_text());data['trajectory'][0]['x']=99;path.write_text(json.dumps(data),encoding='utf-8')
   with self.assertRaises(ValueError):load_and_validate_serialized_snapshot(target,self.manifest)
  with tempfile.TemporaryDirectory() as root:
   target=self.write(root);serialize_snapshot(self.output,target,manifest_hash=self.manifest,protocol_version=VERSION);(target/'combined').mkdir()
   with self.assertRaises(ValueError):load_and_validate_serialized_snapshot(target,self.manifest)
