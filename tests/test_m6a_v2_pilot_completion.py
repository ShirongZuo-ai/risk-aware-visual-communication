import tempfile,json,unittest
from pathlib import Path
from scripts.run_m6a_one_identity import build_one_identity_runtime_config
from scripts.m6a_v2_pilot_completion import *
class T(unittest.TestCase):
 def test_owned_synthetic_32_case_chain(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);cfg=build_one_identity_runtime_config(output_root=root/'out');marker=root/'.owner';marker.write_text('owned');records=[]
   for x in cfg['snapshots']:
    raw=root/'raw'/f"{x['snapshot_id']}.rgb";raw.parent.mkdir(exist_ok=True);raw.write_bytes(bytes(160*120*3));meta=root/'raw'/f"{x['snapshot_id']}.json";meta.write_text(json.dumps({'frame_sha256':__import__('hashlib').sha256(raw.read_bytes()).hexdigest(),'state':{'x':0,'y':0,'yaw_rad':0,'linear_velocity_m_s':.04,'angular_velocity_rad_s':0},'schedule_id':'s','schedule_available_time_s':0,'schedule_segments':[{'start_offset_s':0,'end_offset_s':6,'left_wheel_command_rad_s':2,'right_wheel_command_rad_s':2}],'synthetic_fixture':True}));records.append({'snapshot_id':x['snapshot_id'],'timestamp_s':x['timestamp_s'],'raw_path':str(raw),'metadata_path':str(meta)})
   ev=[process_and_audit_runtime_snapshot(cfg,x,owned_output_root=root,ownership_marker=marker) for x in records];agg=persist_codec_aggregate(cfg,ev,owned_output_root=root,ownership_marker=marker);summary={'summary_sha256':'r'};comp={'runtime_config_sha256':cfg['config_sha256'],'codec_aggregate_sha256':agg['aggregate_sha256'],'runtime_summary_sha256':'r','launch_id':agg['launch_id']};self.assertTrue(validate_pilot_completion({'owner_marker':str(marker)},{'started':True,'timed_out':False,'interrupted':False},summary,agg,comp,owned_output_root=root)['integration_valid'])
