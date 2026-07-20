"""Lazy-import-free adapter that builds M6-A snapshot inputs from mock/Webots readers."""
from scripts.m6a_dual_roi import CurrentState,ScheduleEvidence,SnapshotInput
def build_snapshot(*,manifest_hash,scene,episode_id,seed,snapshot_id,timestamp_s,state_reader,frame_reference,schedule):
 state=CurrentState(**state_reader())
 return SnapshotInput('m6a-byte-fair-v1',manifest_hash,scene,episode_id,seed,snapshot_id,timestamp_s,state,frame_reference,schedule)
