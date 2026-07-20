import hashlib
import re
import tempfile
import unittest
from pathlib import Path

from scripts.m6a_v2_scene_wiring import BASE_WORLD, initialize_v2_scene_before_motion, materialize_m6a_temporary_world
from scripts.run_m6a_one_identity import build_one_identity_runtime_config

class Field:
 def __init__(self,value=None):self.value=value
 def getSFVec3f(self):return list(self.value)
 def setSFVec3f(self,value):self.value=list(value)
 def getSFRotation(self):return list(self.value)
 def setSFRotation(self,value):self.value=list(value)
 def getSFNode(self):return self.value
class Node:
 def __init__(self,translation=None,rotation=None,size=None):
  self.fields={'translation':Field(translation),'rotation':Field(rotation),'geometry':Field(Node(size=size))} if translation is not None else {'size':Field(size)}
  self.reset=False
 def getField(self,name):return self.fields.get(name)
 def resetPhysics(self):self.reset=True
class Children:
 def __init__(self,supervisor):self.supervisor=supervisor;self.items=[]
 def getCount(self):return len(self.items)
 def importMFNodeFromString(self,index,text):
  ident=re.search(r'DEF (M5E_[A-Z0-9_]+) Solid',text).group(1)
  translation=[float(x) for x in re.search(r'translation ([^\n]+)',text).group(1).split()]
  size=[float(x) for x in re.search(r'geometry Box \{ size ([^}]+) \}',text).group(1).split()]
  self.supervisor.nodes[ident]=Node(translation,[0.,0.,1.,0.],size);shape=Node();shape.fields={'geometry':Field(Node(size=size))};self.supervisor.nodes[ident+'_SHAPE']=shape;self.items.append(ident)
class Supervisor:
 def __init__(self,*,missing=None,corrupt=False):
  self.nodes={'ROBOT':Node([9.,9.,9.],[0.,0.,1.,1.])};self.group=Node();self.children=Children(self);self.group.fields={'children':self.children};self.nodes['M5E_OBSTACLES']=self.group;self.corrupt=corrupt
  if missing:self.nodes.pop(missing,None)
 def getFromDef(self,name):
  node=self.nodes.get(name)
  if self.corrupt and name.startswith('M5E_S') and not name.endswith('_SHAPE') and node is not None:node.getField('translation').value[0]+=0.01
  return node
class T(unittest.TestCase):
 def config(self,root):return build_one_identity_runtime_config(output_root=Path(root)/'episode_output')
 def test_initialization_applies_frozen_s1_scene_and_pose(self):
  with tempfile.TemporaryDirectory() as d:
   supervisor=Supervisor();evidence=initialize_v2_scene_before_motion(self.config(d),supervisor)
   self.assertEqual(evidence.seed,600100);self.assertTrue(evidence.scene_initialized_before_motion);self.assertEqual(evidence.frozen_scene_config_sha256,evidence.applied_scene_config_sha256);self.assertEqual(supervisor.children.getCount(),1);self.assertEqual(supervisor.nodes['ROBOT'].getField('translation').getSFVec3f(),[0.,0.,0.])
 def test_initialization_fails_closed_for_missing_def_readback_and_double_authority(self):
  with tempfile.TemporaryDirectory() as d:
   cfg=self.config(d)
   with self.assertRaises(ValueError):initialize_v2_scene_before_motion(cfg,Supervisor(missing='ROBOT'))
   with self.assertRaises(ValueError):initialize_v2_scene_before_motion(cfg,Supervisor(corrupt=True))
   supervisor=Supervisor();initialize_v2_scene_before_motion(cfg,supervisor)
   with self.assertRaises(ValueError):initialize_v2_scene_before_motion(cfg,supervisor)
 def test_temporary_world_is_safe_deterministic_and_wiring_only(self):
  original=hashlib.sha256(BASE_WORLD.read_bytes()).hexdigest()
  with tempfile.TemporaryDirectory() as d:
   cfg=self.config(d);target=Path(d)/'m6a_scene.wbt';evidence=materialize_m6a_temporary_world(cfg,target)
   text=target.read_text(encoding='utf-8');self.assertIn('controller "m6a_trusted_runtime"',text);self.assertIn('supervisor TRUE',text);self.assertEqual(original,hashlib.sha256(BASE_WORLD.read_bytes()).hexdigest());self.assertEqual(evidence.allowed_changes,('controller:m5e_dataset_generator->m6a_trusted_runtime','supervisor:TRUE (preserved)'))
   with self.assertRaises(ValueError):materialize_m6a_temporary_world(cfg,target)
   with self.assertRaises(ValueError):materialize_m6a_temporary_world(cfg,Path(d)/'pilot'/'unsafe.wbt')
