"""Fixed development Worker registrations sharing the same task/container lifecycle."""
from . import policy as deep
from .structure import policy as structure
from .bepipred import policy as bepipred
from ..common import ensure

TOOLS=(deep.TOOL,structure.TOOL,bepipred.TOOL)


def spec(tool_id):
    ensure(tool_id in TOOLS,'PROFILE_NOT_APPROVED','Development Worker is not registered')
    return {deep.TOOL:deep,structure.TOOL:structure,bepipred.TOOL:bepipred}[tool_id]


def result(job,body,files,execution,fault=None):
    if job['tool_id']==deep.TOOL:
        from .deeptmhmm import result as build
    elif job['tool_id']==structure.TOOL:
        from .structure.result import result as build
    else:
        from .bepipred.result import result as build
    return build(job,body,files,execution,fault)
