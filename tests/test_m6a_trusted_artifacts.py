import unittest
from scripts.m6a_trusted_artifacts import *
class T(unittest.TestCase):
 def data(self):
  t=[{'x':0}];c={'r':1};m=(1.,0.);return dict(method='state_only_risk_roi',source_predictor='state_only_predictor',predictor_input_digest='a',predictor_config_digest='b',trajectory=t,trajectory_hash=digest(t),corridor=c,corridor_hash=digest(c),footprint_digest='d',projection_digest='e',rasterization_digest='f',mask_payload=m,mask_hash=digest(m),roi_pixel_count=1,roi_area_ratio=.5,empty=False,full_frame=False,clipped=False,out_of_view=False,generation_pipeline_version=VERSION)
 def test_valid_and_rejections(self):
  self.assertTrue(create_generated_risk_mask(**self.data()))
  for key,val in [('method','combined'),('source_predictor','oracle'),('actual_future_usage',1),('mask_hash','x')]:
   d=self.data();d[key]=val
   with self.assertRaises(ValueError):create_generated_risk_mask(**d)
 def test_config(self):
  a=M6AProjectionConfig();self.assertEqual(a.sha256(),M6AProjectionConfig().sha256())
  with self.assertRaises(ValueError):M6AProjectionConfig(horizon_s=1).validate()
