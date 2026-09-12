"""Repository paths shared by the analysis scripts."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
PANEL = DATA / 'analysis_ready' / 'analysis_ready_with_oil_controls.csv'
TAB = ROOT / 'analysis' / 'outputs' / 'tables'
FIG = ROOT / 'analysis' / 'outputs' / 'figures'
PAPER = ROOT / 'analysis' / 'outputs' / 'manuscript_inputs'   # tables, figures and number macros consumed by the manuscript
for _d in (TAB, FIG, PAPER / 'tables', PAPER / 'figures'):
    _d.mkdir(parents=True, exist_ok=True)
