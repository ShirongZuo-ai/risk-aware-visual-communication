"""Dry-run-only M6-A pilot planner; it never launches Webots."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
PROJECT_ROOT=Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:sys.path.insert(0,str(PROJECT_ROOT))
from scripts.m6a_common import PROJECT_ROOT, METHODS, BUDGETS, SNAPSHOT_PROGRESS, validate
def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,default=PROJECT_ROOT/'docs/results/m6a_manifest.json');p.add_argument('--output-root',default='data/m6a/pilot');p.add_argument('--dry-run',action='store_true',required=True);a=p.parse_args()
 data=json.loads(a.manifest.read_text(encoding='utf-8')); summary=validate(data); pilot=data['episodes']['pilot']
 if len(pilot)!=8 or any(x['split']!='pilot' for x in pilot):raise ValueError('pilot identities are not frozen')
 if a.output_root.startswith('data/m5') or a.output_root.startswith('results/m5'):raise ValueError('M5 output roots are forbidden')
 root=PROJECT_ROOT/a.output_root
 if root.exists() and any(root.iterdir()):raise FileExistsError('refusing to overwrite pilot output')
 out={'manifest_sha256':hashlib.sha256(a.manifest.read_bytes()).hexdigest(),'pilot_identities':[x['episode_id'] for x in pilot],'expected_episodes':8,'expected_frames':8*len(SNAPSHOT_PROGRESS),'expected_methods':len(METHODS),'expected_budgets':len(BUDGETS),'expected_cases':8*len(SNAPSHOT_PROGRESS)*len(METHODS)*len(BUDGETS),'webots_started':False}
 print(json.dumps(out,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
