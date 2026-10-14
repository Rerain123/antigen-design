"""Linux wrapper for the frozen W1 supervisor entry point."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from t01_phase1_real.linux_service import install_platform_modules

install_platform_modules()

from t01_phase1_real.supervisor import main


if __name__ == "__main__":
    main()
