"""Internal fixed engineering worker entry point."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from t01_phase1_real.engineering_worker import main

if __name__ == '__main__': raise SystemExit(main())
