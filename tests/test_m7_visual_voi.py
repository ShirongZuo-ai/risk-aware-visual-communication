import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import matplotlib.pyplot as plt
import numpy as np

from scripts.m6a_trusted_artifacts import digest
from scripts.m7_visual_voi import (
    DISTORTION_WEIGHTS, QUALITY_LADDER, WEIGHTS, VisualVoIInput,
    _high_quality_mask, allocate_visual_voi, component_maps, stratified_ci,
    _save_figure, reproduction_gate, validate_allocation_provenance,
)


class M7VisualVoIAllocatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        y,x=np.indices((120,160));image=np.stack(((2*x+y)%256,(x+2*y)%256,(3*x+y)%256),axis=-1).astype(np.uint8)
        snapshot=SimpleNamespace(snapshot_id='0',image=image,raw_image_sha256=hashlib.sha256(image.tobytes()).hexdigest())
        state=np.zeros((120,160),float);state[40:70,50:90]=1
        command=np.zeros_like(state);command[45:80,70:120]=1
        cls.value=VisualVoIInput.create(snapshot=snapshot,state_mask=tuple(state.ravel()),command_mask=tuple(command.ravel()),state_mask_sha256=digest(tuple(state.ravel())),command_mask_sha256=digest(tuple(command.ravel())))

    def test_frozen_weights_and_quality_ladder(self):
        self.assertEqual(WEIGHTS,{'risk':.25,'trajectory_coverage':.25,'visibility_gain':.25,'uncertainty':.25})
        self.assertEqual(DISTORTION_WEIGHTS,{'visible_boundary':.5,'projected_corridor':.3,'whole_tile':.2})
        self.assertEqual(QUALITY_LADDER,(1,15,35,55,75,95))

    def test_component_maps_are_finite_and_bounded(self):
        maps=component_maps(self.value);self.assertEqual(set(maps),{'risk','trajectory_coverage','visibility_gain','uncertainty','task_weight'})
        self.assertTrue(all(len(items)==48 for items in maps.values()));self.assertTrue(all(0<=item<=1 for items in maps.values() for item in items))

    def test_allocator_is_deterministic_and_byte_fair(self):
        first=allocate_visual_voi(self.value,'high',34871);second=allocate_visual_voi(self.value,'high',34871)
        self.assertEqual(first.case_digest,second.case_digest);self.assertEqual(first.payload,second.payload);self.assertLessEqual(first.charged_bytes,34871)
        self.assertEqual(first.charged_bytes,len(first.payload)+first.metadata_bytes);validate_allocation_provenance(first.provenance)

    def test_tighter_budget_never_exceeds_target(self):
        case=allocate_visual_voi(self.value,'severe',31466);self.assertLessEqual(case.charged_bytes,31466)

    def test_high_quality_is_relative_to_frame_background(self):
        qualities=(5,)*47+(35,);mask=_high_quality_mask(qualities)
        self.assertEqual(int(mask.sum()),400)

    def test_mask_digest_tamper_rejected(self):
        with self.assertRaises(ValueError):
            VisualVoIInput.create(snapshot=SimpleNamespace(snapshot_id='0',image=self.value.image,raw_image_sha256=self.value.raw_image_sha256),state_mask=self.value.state_mask,command_mask=self.value.command_mask,state_mask_sha256='0'*64,command_mask_sha256=self.value.command_mask_sha256)

    def test_evaluator_and_future_inputs_rejected(self):
        snapshot=SimpleNamespace(snapshot_id='0',image=self.value.image,raw_image_sha256=self.value.raw_image_sha256)
        for field in ('evaluator_only_geometry','actual_future','tcobr_labels','evaluation_mask'):
            with self.subTest(field=field),self.assertRaises(ValueError):
                VisualVoIInput.create(snapshot=snapshot,state_mask=self.value.state_mask,command_mask=self.value.command_mask,state_mask_sha256=self.value.state_mask_sha256,command_mask_sha256=self.value.command_mask_sha256,**{field:{}})

    def test_provenance_tamper_rejected_even_with_plausible_fields(self):
        case=allocate_visual_voi(self.value,'low',32374);tampered=copy.deepcopy(case.provenance);tampered['charged_bytes']-=1
        with self.assertRaises(ValueError):validate_allocation_provenance(tampered)

    def test_nonzero_leakage_rejected(self):
        bad=copy.copy(self.value);object.__setattr__(bad,'actual_future_usage',1)
        with self.assertRaises(ValueError):allocate_visual_voi(bad,'low',32374)


class M7VisualVoIStatisticsTests(unittest.TestCase):
    def test_scene_stratified_bootstrap_is_deterministic(self):
        rows=[{'scene':'M7C1','effect':.1},{'scene':'M7C1','effect':.2},{'scene':'M7C2','effect':-.1},{'scene':'M7C2','effect':.3}]
        self.assertEqual(stratified_ci(rows,'effect'),stratified_ci(rows,'effect'))

    def test_empty_bootstrap_is_explicitly_undefined(self):
        self.assertEqual(stratified_ci([],'effect')['n'],0)

    def test_reproduction_gate_allows_legitimate_duplicate_allocations(self):
        same={'canonical_digest':'same'}
        self.assertTrue(reproduction_gate([same]*256,double_run_match=True))
        self.assertFalse(reproduction_gate([same]*255,double_run_match=True))
        self.assertFalse(reproduction_gate([same]*256,double_run_match=False))

    def test_svg_output_is_canonical_lf_without_trailing_whitespace(self):
        with tempfile.TemporaryDirectory() as directory:
            fig,axis=plt.subplots();axis.plot([0,1],[0,1])
            base=Path(directory)/'figure';_save_figure(fig,base)
            payload=base.with_suffix('.svg').read_bytes()
            self.assertNotIn(b'\r\n',payload)
            self.assertTrue(payload.endswith(b'\n'))
            self.assertTrue(all(line==line.rstrip() for line in payload.splitlines()))
