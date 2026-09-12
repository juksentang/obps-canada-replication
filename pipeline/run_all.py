#!/usr/bin/env python3
"""Run the data-construction pipeline in order (raw GHGRP, CIPO and Statistics Canada inputs -> analysis-ready panels).
Usage: python pipeline/run_all.py [--from N] [--to N]
Raw inputs must first be downloaded with data/download.sh (see data/README.md). Each step is a stand-alone script; a failure stops the run."""
import argparse, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = sorted(p for p in HERE.glob('[0-9][0-9]_*.py'))

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--from', dest='start', type=int, default=1, help='first step number to run (default 1)')
    ap.add_argument('--to', dest='stop', type=int, default=len(STEPS), help='last step number to run')
    a = ap.parse_args()
    for p in STEPS:
        n = int(p.name[:2])
        if n < a.start or n > a.stop: continue
        t0 = time.time(); print(f'==> {p.name}', flush=True)
        r = subprocess.run([sys.executable, str(p)], cwd=str(HERE))
        print(f'<== {p.name} exit {r.returncode} ({time.time() - t0:.0f}s)', flush=True)
        if r.returncode != 0: sys.exit(r.returncode)

if __name__ == '__main__':
    main()
