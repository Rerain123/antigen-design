"""Internal registered Worker supervisor. Use t01_runtime.py to submit jobs."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from t01_phase1_real.development.supervisor import main
if __name__=='__main__':main()
