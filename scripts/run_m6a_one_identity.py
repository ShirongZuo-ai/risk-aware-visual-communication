"""Preflight-only first-pilot launcher preparation; deliberately never launches Webots."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from scripts.m6a_common import PROJECT_ROOT,VERSION,METHODS,BUDGETS,SNAPSHOT_PROGRESS,validate
def first_pilot(manifest_path):
 data=json.loads(Path(manifest_path).read_text(encoding='utf-8'));validate(data)
 rows=data['episodes']['pilot'];return data,sorted(rows,key=lambda x:(x['scenario_id'],x['seed'],x['episode_id']))[0]
def plan(manifest_path):
 data,item=first_pilot(manifest_path);return {'manifest_sha256':hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest(),'identity':item,'expected_episodes':1,'expected_snapshots':4,'expected_methods':len(METHODS),'expected_budgets':len(BUDGETS),'future_reconstruction_cases':32,'webots_started':False,'execution_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,default=PROJECT_ROOT/'docs/results/m6a_manifest.json');p.add_argument('--dry-run',action='store_true');p.add_argument('--preflight',action='store_true');a=p.parse_args()
 if a.dry_run==a.preflight:p.error('choose exactly one of --dry-run or --preflight')
 out=plan(a.manifest);out['mode']='preflight' if a.preflight else 'dry-run';print(json.dumps(out,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
