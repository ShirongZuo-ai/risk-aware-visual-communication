import json,tempfile,unittest
from pathlib import Path
from scripts.run_m6a_one_identity import build_one_identity_runtime_config,materialize_runtime_config,load_v2_runtime_config
class T(unittest.TestCase):
 def test_build_and_materialize(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);cfg=build_one_identity_runtime_config(output_root=root/'preflight_output');p=materialize_runtime_config(cfg,root/'runtime.json');raw=p.read_bytes();expected=(json.dumps(cfg,sort_keys=True,separators=(',',':'))+'\n').encode('utf-8');self.assertEqual(raw,expected);self.assertNotIn(b'\r\n',raw);self.assertEqual(load_v2_runtime_config(json.loads(raw))['episode_id'],'m6a_pilot_s1_seed600100')
 def test_tampered_v2_source_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   cfg=build_one_identity_runtime_config(output_root=Path(d)/'preflight_output');cfg['schedule']['segments'][0]['left_rad_s']+=0.01;cfg['config_sha256']=__import__('scripts.m6a_trusted_artifacts',fromlist=['digest']).digest({k:v for k,v in cfg.items() if k!='config_sha256'})
   with self.assertRaises(ValueError):load_v2_runtime_config(cfg)
