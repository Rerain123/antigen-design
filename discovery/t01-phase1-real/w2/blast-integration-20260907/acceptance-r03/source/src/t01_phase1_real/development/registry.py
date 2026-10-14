"""Fixed development Worker registrations sharing the same task/container lifecycle."""
from . import policy as deep
from .structure import policy as structure
from .bepipred import policy as bepipred
from .netmhc import policy as netmhc
from .blast import policy as blast
from .epitope_map import policy as epitope_map
from .glycosylation import policy as glycosylation
from ..common import ensure

TOOLS=(deep.TOOL,structure.TOOL,bepipred.TOOL,netmhc.TOOL,blast.TOOL,epitope_map.TOOL,glycosylation.TOOL)


def spec(tool_id):
    ensure(tool_id in TOOLS,'PROFILE_NOT_APPROVED','Development Worker is not registered')
    return {deep.TOOL:deep,structure.TOOL:structure,bepipred.TOOL:bepipred,netmhc.TOOL:netmhc,blast.TOOL:blast,epitope_map.TOOL:epitope_map,
        glycosylation.TOOL:glycosylation}[tool_id]


def result(job,body,files,execution,fault=None):
    if job['tool_id']==deep.TOOL:
        from .deeptmhmm import result as build
    elif job['tool_id']==structure.TOOL:
        from .structure.result import result as build
    elif job['tool_id']==bepipred.TOOL:
        from .bepipred.result import result as build
    elif job['tool_id']==netmhc.TOOL:
        from .netmhc.result import result as build
    elif job['tool_id']==blast.TOOL:
        from .blast.result import result as build
    elif job['tool_id']==epitope_map.TOOL:
        from .epitope_map.result import result as build
    else:
        from .glycosylation.result import result as build
    return build(job,body,files,execution,fault)
