import tempfile,json,unittest
from pathlib import Path
from scripts.run_m6a_one_identity import build_one_identity_runtime_config,materialize_runtime_config
from scripts.m6a_v2_pilot_completion import *
from scripts.m6a_v2_runtime_evidence import persist_runtime_manifest
from tests.test_m6a_v2_runtime_evidence import RuntimeManifestTests
class T(unittest.TestCase):
 def test_owned_synthetic_32_case_chain(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);cfg=build_one_identity_runtime_config(output_root=root/'out');marker=root/'.owner';marker.write_text('owned');records=[]
   for x in cfg['snapshots']:
    raw=root/'raw'/f"{x['snapshot_id']}.rgb";raw.parent.mkdir(exist_ok=True);raw.write_bytes(bytes(160*120*3));meta=root/'raw'/f"{x['snapshot_id']}.json";meta.write_text(json.dumps({'frame_sha256':__import__('hashlib').sha256(raw.read_bytes()).hexdigest(),'state':{'x':0,'y':0,'yaw_rad':0,'linear_velocity_m_s':.04,'angular_velocity_rad_s':0},'schedule_id':'s','schedule_available_time_s':0,'schedule_segments':[{'start_offset_s':0,'end_offset_s':6,'left_wheel_command_rad_s':2,'right_wheel_command_rad_s':2}],'synthetic_fixture':True}));records.append({'snapshot_id':x['snapshot_id'],'timestamp_s':x['timestamp_s'],'raw_path':str(raw),'metadata_path':str(meta)})
   ev=[process_and_audit_runtime_snapshot(cfg,x,owned_output_root=root,ownership_marker=marker) for x in records];agg=persist_codec_aggregate(cfg,ev,owned_output_root=root,ownership_marker=marker);summary={'summary_sha256':'r'};comp={'runtime_config_sha256':cfg['config_sha256'],'codec_aggregate_sha256':agg['aggregate_sha256'],'runtime_summary_sha256':'r','launch_id':agg['launch_id']};self.assertTrue(validate_pilot_completion({'owner_marker':str(marker)},{'started':True,'timed_out':False,'interrupted':False},summary,agg,comp,owned_output_root=root)['integration_valid'])

 def test_aggregate_validation_reloads_and_tamper_fails(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);cfg=build_one_identity_runtime_config(output_root=root/'out');marker=root/'.owner';marker.write_text('owned');records=[]
   for x in cfg['snapshots']:
    raw=root/'raw'/f"{x['snapshot_id']}.rgb";raw.parent.mkdir(exist_ok=True);raw.write_bytes(bytes(160*120*3));meta=root/'raw'/f"{x['snapshot_id']}.json";meta.write_text(json.dumps({'frame_sha256':__import__('hashlib').sha256(raw.read_bytes()).hexdigest(),'state':{'x':0,'y':0,'yaw_rad':0,'linear_velocity_m_s':.04,'angular_velocity_rad_s':0},'schedule_id':'s','schedule_available_time_s':0,'schedule_segments':[{'start_offset_s':0,'end_offset_s':6,'left_wheel_command_rad_s':2,'right_wheel_command_rad_s':2}],'synthetic_fixture':True}));records.append({'snapshot_id':x['snapshot_id'],'timestamp_s':x['timestamp_s'],'raw_path':str(raw),'metadata_path':str(meta)})
   aggregate=persist_codec_aggregate(cfg,[process_and_audit_runtime_snapshot(cfg,x,owned_output_root=root,ownership_marker=marker) for x in records],owned_output_root=root,ownership_marker=marker);identity={'launch_id':'l','attempt_id':'a','identity_id':cfg['episode_id'],'scene_id':cfg['scene'],'seed':cfg['seed']};report=persist_codec_aggregate_validation(root/'codec_aggregate_validation.json',cfg,root/'codec_aggregate.json',root=root,identity=identity)
   self.assertEqual(load_codec_aggregate_validation(root/'codec_aggregate_validation.json',cfg,root=root,identity=identity)['report_sha256'],report['report_sha256']);data=json.loads((root/'codec_aggregate.json').read_text());data['case_count']=31;(root/'codec_aggregate.json').write_text(json.dumps(data))
   with self.assertRaises(ValueError):load_codec_aggregate_validation(root/'codec_aggregate_validation.json',cfg,root=root,identity=identity)

 def test_completion_persists_and_reloads_joint_report(self):
  helper=RuntimeManifestTests();temporary,root,cfg,identity=helper.fixture();self.addCleanup(temporary.cleanup)
  persist_runtime_manifest(root/'runtime_artifacts.json',identity,root,runtime_config=cfg,summary_path=root/'summary.json',status_path=root/'status.json',diagnostic_path=root/'diagnostic.json')
  marker=root/'.owner';marker.write_text('owned');runtime_path=materialize_runtime_config(cfg,root/'runtime.json');spec={'runtime_config':{'path':str(runtime_path)},'summary_path':str(root/'summary.json'),'runtime_manifest_path':str(root/'runtime_artifacts.json'),'aggregate_validation_path':str(root/'codec_aggregate_validation.json'),'joint_report_path':str(root/'joint_validation.json'),'owner_marker':str(marker)}
  result=process_completed_pilot_launch(spec,{'started':True,'timed_out':False,'interrupted':False},owned_output_root=root)
  self.assertTrue(result['integration_valid']);self.assertTrue((root/'joint_validation.json').is_file());self.assertTrue(load_joint_validation_report(root/'joint_validation.json',cfg,root=root)['joint_sha256'])
