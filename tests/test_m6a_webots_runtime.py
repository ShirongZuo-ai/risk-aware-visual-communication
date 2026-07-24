import tempfile,unittest
from pathlib import Path
from navigation.trajectory_prediction import CommandSegment
from scripts.m6a_dual_roi import CurrentState,ScheduleEvidence
from scripts.m6a_trusted_artifacts import M6AProjectionConfig
from scripts.m6a_webots_adapter import CameraFrame,M6ARuntimeConfig,StateSample,run_m6a_webots_episode
class Facade:
 def __init__(self,times):self.times=iter(times)
 def step(self):return next(self.times,None)
class RuntimeTests(unittest.TestCase):
 def make(self,root,times=(0.,1.,2.,3.),available=0.):
  state=CurrentState(0,0,0,.1,0);now=[0.]
  facade=Facade(times)
  original=facade.step
  def step():now[0]=original();return now[0]
  facade.step=step
  config=M6ARuntimeConfig('m','S1','e',1,(('0',0.),('1',1.),('2',2.),('3',3.)),Path(root),M6AProjectionConfig())
  schedule=ScheduleEvidence('p',available,(CommandSegment(0,4,1,1),))
  return config,facade,lambda:StateSample(state,now[0]),lambda:CameraFrame(bytes(160*120*3),now[0]),schedule
 def test_mocked_episode_writes_four_trusted_snapshots(self):
  with tempfile.TemporaryDirectory() as root:
   c,f,s,frame,q=self.make(root,times=(0.,1.,2.,3.,4.));summary=run_m6a_webots_episode(c,f,state_reader=s,frame_reader=frame,predefined_schedule=q)
   self.assertTrue(summary.success);self.assertEqual(summary.actual_snapshot_count,4);self.assertEqual(summary.method_set,('command_conditioned_risk_roi','state_only_risk_roi'));self.assertTrue(all(Path(x).is_dir() for x in summary.serialized_snapshot_paths))
 def test_late_schedule_and_alignment_fail_closed(self):
  with tempfile.TemporaryDirectory() as root:
   c,f,s,frame,q=self.make(root,available=1)
   with self.assertRaises(ValueError):run_m6a_webots_episode(c,f,state_reader=s,frame_reader=frame,predefined_schedule=q)
  with tempfile.TemporaryDirectory() as root:
   c,f,s,frame,q=self.make(root,times=(.1,1,2,3))
   with self.assertRaises(ValueError):run_m6a_webots_episode(c,f,state_reader=s,frame_reader=frame,predefined_schedule=q)
