"""Linux wrapper for the frozen W1 engineering Worker entry point."""

from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from t01_phase1_real.linux_service import install_platform_modules

install_platform_modules()

# The frozen Windows fixture reads this flag only when spawning its bounded
# child-process test. Zero is the POSIX equivalent and keeps the source frozen.
if not hasattr(subprocess, "CREATE_NO_WINDOW"):
    subprocess.CREATE_NO_WINDOW = 0

from t01_phase1_real.engineering_worker import main


if __name__ == "__main__":
    raise SystemExit(main())
