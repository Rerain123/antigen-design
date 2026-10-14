"""Repository entry point for the portable, offline tool contract validator."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "工作流设计/02-数据契约/tool-interface-v0.1/validate.py"), run_name="__main__")
