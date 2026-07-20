"""Webots-discoverable M6-A controller wrapper; requires M6A_RUNTIME_CONFIG."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.m6a_webots_adapter import main_m6a_webots_controller
raise SystemExit(main_m6a_webots_controller())
