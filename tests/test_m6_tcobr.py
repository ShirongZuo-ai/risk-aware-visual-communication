import unittest
from dataclasses import asdict

import cv2
import numpy as np

from navigation.trajectory_prediction import CommandSegment
from perception.camera_models import CameraExtrinsics, CameraIntrinsics
from perception.camera_projection import project_obstacle_box
from scripts.m6_tcobr import evaluate_tcobr_case, validate_tcobr_evidence
from scripts.m6a_dual_roi import CurrentState, ScheduleEvidence
from simulator.adapters.webots_camera_adapter import DEVICE_TO_OPTICAL_ROTATION
from simulator.m5e_scenarios import generate_scenario
from perception.camera_models import ObstacleBox3D


class TCOBRTests(unittest.TestCase):
    def fixture(self):
        intrinsics = CameraIntrinsics.from_horizontal_fov(160, 120, 0.84, 0.005)
        extrinsics = CameraExtrinsics.from_camera_pose_in_world(((1.,0.,0.),(0.,1.,0.),(0.,0.,1.)), (0.,0.,0.03), DEVICE_TO_OPTICAL_ROTATION)
        context = {"intrinsics":asdict(intrinsics),"extrinsics":asdict(extrinsics),"camera_world_position":[0.,0.,0.03],"camera_to_world_rotation":[[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]]}
        spec = generate_scenario("S1", "formal", 620100).obstacle_specs[0]
        projection = project_obstacle_box(ObstacleBox3D(spec.obstacle_id,*spec.center_world,*spec.size_xyz),intrinsics,extrinsics)
        polygon=np.asarray([(round(p.u_px),round(p.v_px)) for p in projection.clipped_polygon],dtype=np.int32)
        image=np.zeros((120,160,3),dtype=np.uint8);cv2.polylines(image,[polygon],True,(255,255,255),1)
        state=CurrentState(.20,0.,0.,.04,0.)
        schedule=ScheduleEvidence("frozen",0.,(CommandSegment(0.,2.,2.,2.),))
        return image,state,schedule,context

    def evaluate(self,reconstruction):
        image,state,schedule,context=self.fixture()
        return evaluate_tcobr_case(scene="S1",seed=620100,snapshot_id="0",method="state_only_risk_roi",budget="severe",original=image,reconstruction=reconstruction,state=state,schedule=schedule,snapshot_time_s=1.216,camera_context=context,original_sha256="a"*64,reconstruction_sha256="b"*64)

    def test_perfect_boundary_is_recalled(self):
        image,*_=self.fixture(); evidence=self.evaluate(image.copy())
        self.assertGreaterEqual(evidence.eligible_count,1);self.assertEqual(evidence.tcobr,1.0);validate_tcobr_evidence(evidence)

    def test_missing_boundary_is_not_recalled(self):
        image,*_=self.fixture(); evidence=self.evaluate(np.zeros_like(image))
        self.assertGreaterEqual(evidence.eligible_count,1);self.assertEqual(evidence.tcobr,0.0)

    def test_canonical_tamper_rejected(self):
        image,*_=self.fixture(); value=asdict(self.evaluate(image));value["recalled_count"]=0
        with self.assertRaises(ValueError):validate_tcobr_evidence(value)

    def test_invalid_camera_context_rejected(self):
        image,state,schedule,_=self.fixture()
        with self.assertRaises(ValueError):evaluate_tcobr_case(scene="S1",seed=620100,snapshot_id="0",method="state_only_risk_roi",budget="severe",original=image,reconstruction=image,state=state,schedule=schedule,snapshot_time_s=1.216,camera_context={},original_sha256="a",reconstruction_sha256="b")

