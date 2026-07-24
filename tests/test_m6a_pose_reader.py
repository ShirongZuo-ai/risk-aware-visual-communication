import unittest
from scripts.m6a_webots_adapter import WebotsCurrentStateReader
class N:
 def getPosition(self):return [1,2,0]
 def getOrientation(self):return [0.877582562,-0.4792,0.015,0.479425539,0.8773,-0.018,-0.004,0.023,0.9997]
class M:
 def __init__(self,x):self.x=x
 def getVelocity(self):return self.x
class S:
 def __init__(self):self.t=1
 def getFromDef(self,x):return N() if x=='EPUCK' else None
 def getDevice(self,x):return M(2 if x.startswith('left') else 4)
 def getTime(self):return self.t
class T(unittest.TestCase):
 def test_current_pose_and_causal_wheels(self):
  s=S();r=WebotsCurrentStateReader(s);x=r();self.assertEqual((x.state.x,x.state.y),(1,2));self.assertAlmostEqual(x.state.yaw_rad,.5);self.assertAlmostEqual(x.state.linear_velocity_m_s,.06);self.assertAlmostEqual(x.state.angular_velocity_rad_s,.02/.052*2)
  with self.assertRaises(ValueError):r()
 def test_missing_def_fails(self):
  s=S();s.getFromDef=lambda x:None
  with self.assertRaises(ValueError):WebotsCurrentStateReader(s)
