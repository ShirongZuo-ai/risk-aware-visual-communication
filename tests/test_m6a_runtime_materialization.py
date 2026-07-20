import json,tempfile,unittest
from pathlib import Path
from scripts.run_m6a_one_identity import build_one_identity_runtime_config,materialize_runtime_config
from scripts.m6a_common import PROJECT_ROOT
class T(unittest.TestCase):
 def test_build_and_materialize(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);world=root/'source.wbt';world.write_text('world');source=root/'episode.json';identity={'split':'pilot','scenario_id':'S1','seed':600100,'episode_id':'m6a_pilot_s1_seed600100'};source.write_text(json.dumps({'identity':identity,'snapshot_times':[.2,.4,.6,.8],'schedule':{'schedule_id':'p','available_time_s':0,'segments':[{'start_offset_s':0,'end_offset_s':2,'left_wheel_command_rad_s':1,'right_wheel_command_rad_s':1}]}}));cfg=build_one_identity_runtime_config(PROJECT_ROOT/'docs/results/m6a_manifest.json',source,output_root=root/'preflight_output',source_world=world);p=materialize_runtime_config(cfg,root/'runtime.json');self.assertEqual(json.loads(p.read_text())['episode_id'],identity['episode_id'])
