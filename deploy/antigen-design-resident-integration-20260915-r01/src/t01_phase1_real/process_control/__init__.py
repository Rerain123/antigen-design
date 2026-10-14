"""Cross-platform owned-process primitives used by the durable runtime."""

import os

if os.name == "nt":
    from .windows import *  # noqa: F401,F403
elif os.name == "posix":
    from .posix import *  # noqa: F401,F403
else:  # pragma: no cover
    raise RuntimeError(f"Unsupported process-control platform: {os.name}")

