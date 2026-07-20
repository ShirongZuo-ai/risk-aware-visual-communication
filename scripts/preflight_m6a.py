"""Validate M6-A's frozen manifest without generating formal evidence."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0, str(PROJECT_ROOT))
from scripts.m6a_common import validate
def main() -> int:
 p=argparse.ArgumentParser(); p.add_argument('--manifest',type=Path,default=PROJECT_ROOT/'docs/results/m6a_manifest.json'); p.add_argument('--formal-output-root',default='results/m6a_formal') ; a=p.parse_args()
 root=(PROJECT_ROOT/a.formal_output_root).resolve()
 if PROJECT_ROOT not in root.parents: raise ValueError('formal output root escapes repository')
 if root.exists() and any(root.iterdir()): raise ValueError('formal output directory is not clean; formal run is blocked')
 summary=validate(json.loads(a.manifest.read_text(encoding='utf-8'))); summary.update({'formal_output_clean':True,'formal_run_started':False,'manifest':str(a.manifest.relative_to(PROJECT_ROOT))})
 print(json.dumps(summary,sort_keys=True)); return 0
if __name__ == '__main__': raise SystemExit(main())
