import json,tempfile,unittest
from pathlib import Path
from scripts.m6a_webots_adapter import WebotsRobotFacade,webots_bgra_to_rgb,load_m6a_runtime_config
class Camera:
 def enable(self,t):self.t=t
 def getImage(self):return bytes([3,2,1,0])*19200
class Robot:
 def __init__(self):self.t=0
 def getBasicTimeStep(self):return 32
 def getDevice(self,n):return Camera() if n=='camera' else None
 def step(self,t):self.t+=.032;return 0
 def getTime(self):return self.t
class T(unittest.TestCase):
 def test_facade_and_bgra_conversion(self):
  f=WebotsRobotFacade(Robot(),pose_reader=lambda:{'x':0,'y':0,'yaw_rad':0,'linear_velocity_m_s':.1,'angular_velocity_rad_s':0})
  self.assertEqual(f.step(),.032);self.assertEqual(f.frame_sample().rgb[:3],bytes((1,2,3)))
  with self.assertRaises(ValueError):webots_bgra_to_rgb(b'x')
 def test_pilot_config_rejects_forbidden_split(self):
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)/'c.json';data={'protocol_version':'m6a-byte-fair-v1','manifest_hash':'m','split':'pilot','scene':'S1','episode_id':'p','seed':1,'snapshots':[{'snapshot_id':str(i),'timestamp_s':float(i)} for i in range(4)],'schedule':{'schedule_id':'q','available_time_s':0,'segments':[{'start_offset_s':0,'end_offset_s':2,'left_wheel_command_rad_s':1,'right_wheel_command_rad_s':1}]},'output_root':root,'projection_config':{}}
   p.write_text(json.dumps(data));self.assertTrue(load_m6a_runtime_config(p,expected_manifest_hash='m'))
   data['split']='formal';p.write_text(json.dumps(data));
   with self.assertRaises(ValueError):load_m6a_runtime_config(p,expected_manifest_hash='m')
