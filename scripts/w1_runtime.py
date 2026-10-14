"""Public local CLI for the independent W1 engineering runtime."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from t01_phase1_real.cli import main

if __name__ == '__main__': raise SystemExit(main())
