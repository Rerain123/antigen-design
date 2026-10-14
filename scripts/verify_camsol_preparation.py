"""Run the specified N=200, N_S=100000 sampler on defined Eq1 only."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from t01_phase1_real.development.developability.calibration import prepare
from t01_phase1_real.common import encode
if __name__=='__main__':
    path=ROOT/'reports/remaining-tools-20260928/camsol-preparation.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    result=prepare();path.write_bytes(encode(result));print(encode(result).decode())
