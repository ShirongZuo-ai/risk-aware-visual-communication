"""Small deterministic codec-only smoke check; not an M6-A pilot result."""
from __future__ import annotations
import csv,json,sys
from pathlib import Path
from PIL import Image
PROJECT_ROOT=Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0,str(PROJECT_ROOT))
from compression.spatial_allocation import build_tile_cache, match_spatial_allocations_to_budgets
from compression.tile_scoring import TileScoreMap
from compression.tiled_jpeg import DEFAULT_M5_GRID
from scripts.m6a_common import BUDGETS, METHODS

def image_for(index:int)->Image.Image:
 return Image.new('RGB',(160,120),((index*37)%256,(index*71)%256,(index*19)%256))
def score(method:str,index:int)->TileScoreMap:
 values=tuple(float(((tile*(3 if method.startswith('command') else 5)+index)%17))/16.0 for tile in range(48))
 return TileScoreMap(method,DEFAULT_M5_GRID,values,'deterministic codec-only smoke score')
def main()->int:
 output=PROJECT_ROOT/'results/m6a_allocation_smoke'; output.mkdir(parents=True,exist_ok=True)
 rows=[]
 for index in range(2):
  cache=build_tile_cache(image_for(index))
  for method in METHODS:
   for match in match_spatial_allocations_to_budgets(score(method,index),cache,BUDGETS.values()):
    rows.append({'smoke_frame':index,'method':method,'target_bytes':match.target_bytes,'actual_total_bytes':match.actual_total_bytes,'absolute_byte_error':match.unused_bytes,'relative_byte_error':match.unused_bytes/match.target_bytes,'within_budget':match.actual_total_bytes<=match.target_bytes,'container_overhead_bytes':match.container_overhead_bytes,'roi_pixel_count':'not_applicable_codec_smoke','actual_future_trajectory_used':False})
 with (output/'m6a_allocation_smoke.csv').open('w',newline='',encoding='utf-8') as handle:
  writer=csv.DictWriter(handle,fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
 over=sum(not row['within_budget'] for row in rows)
 summary={'kind':'codec_only_smoke_not_pilot_evidence','frames':2,'cases':len(rows),'over_budget':over,'actual_future_trajectory_used':False,'formal_run_started':False}
 (output/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps(summary,sort_keys=True)); return 0 if not over else 1
if __name__=='__main__': raise SystemExit(main())
