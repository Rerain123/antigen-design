"""Linux entry point that preserves the frozen Windows W1 modules byte-for-byte."""

from __future__ import annotations

import sys
import types
from pathlib import Path


def install_platform_modules() -> None:
    if sys.platform != "linux":
        raise RuntimeError("The Linux service entry point requires Linux")
    from . import linux_files
    from .process_control import posix

    package = __package__ or "t01_phase1_real"
    sys.modules[package + ".files"] = linux_files
    sys.modules[package + ".winprocess"] = posix

    # Execute the frozen runtime under its stable import identity, changing only
    # its former Windows admission check. Storage and process imports above are
    # already bound to qualified POSIX implementations.
    path = Path(__file__).with_name("runtime.py")
    source = path.read_text(encoding="utf-8")
    old = "ensure(os.name=='nt','PROFILE_NOT_APPROVED','This local executor is qualified on Windows only')"
    new = "ensure(os.name=='posix','PROFILE_NOT_APPROVED','This Linux executor requires POSIX')"
    if source.count(old) != 1:
        raise RuntimeError("Frozen runtime admission statement differs")
    module = types.ModuleType(package + ".runtime")
    module.__file__ = str(path)
    module.__package__ = package
    sys.modules[module.__name__] = module
    exec(compile(source.replace(old, new), str(path), "exec"), module.__dict__)


def main() -> int:
    install_platform_modules()
    from .service_api.transport import main as service_main
    return service_main()


if __name__ == "__main__":
    raise SystemExit(main())
