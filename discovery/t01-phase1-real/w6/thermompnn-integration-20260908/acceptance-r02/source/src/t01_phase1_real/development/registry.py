"""Fixed development Worker registrations sharing the same task/container lifecycle."""
from . import policy as deep
from .structure import policy as structure
from .bepipred import policy as bepipred
from .netmhc import policy as netmhc
from .blast import policy as blast
from .epitope_map import policy as epitope_map
from .glycosylation import policy as glycosylation
from .homology import policy as homology
from .domains import policy as domains
from .developability import policy as developability
from .wt_draft import policy as wt_draft
from .proteinmpnn import policy as proteinmpnn
from .esm_if1 import policy as esm_if1
from .design_backend import policy as design_backend
from .thermompnn import policy as thermompnn
from ..common import ensure

TOOLS=(deep.TOOL,structure.TOOL,bepipred.TOOL,netmhc.TOOL,blast.TOOL,epitope_map.TOOL,glycosylation.TOOL,homology.TOOL,
    domains.TOOL,developability.TOOL,wt_draft.TOOL,proteinmpnn.TOOL,esm_if1.TOOL,design_backend.TOOL,thermompnn.TOOL)


def spec(tool_id):
    ensure(tool_id in TOOLS,'PROFILE_NOT_APPROVED','Development Worker is not registered')
    return {deep.TOOL:deep,structure.TOOL:structure,bepipred.TOOL:bepipred,netmhc.TOOL:netmhc,blast.TOOL:blast,epitope_map.TOOL:epitope_map,
        glycosylation.TOOL:glycosylation,homology.TOOL:homology,domains.TOOL:domains,developability.TOOL:developability,
        wt_draft.TOOL:wt_draft,proteinmpnn.TOOL:proteinmpnn,esm_if1.TOOL:esm_if1,design_backend.TOOL:design_backend,
        thermompnn.TOOL:thermompnn}[tool_id]


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
    elif job['tool_id']==domains.TOOL:
        from .domains.service import result as build
    elif job['tool_id']==homology.TOOL:
        from .homology.result import result as build
    elif job['tool_id']==developability.TOOL:
        from .developability.service import result as build
    elif job['tool_id']==wt_draft.TOOL:
        from .wt_draft.service import result as build
    elif job['tool_id']==proteinmpnn.TOOL:
        from .proteinmpnn.result import result as build
    elif job['tool_id']==design_backend.TOOL:
        from .design_backend.service import result as build
    elif job['tool_id']==esm_if1.TOOL:
        from .esm_if1.result import result as build
    elif job['tool_id']==thermompnn.TOOL:
        from .thermompnn.result import result as build
    else:
        from .glycosylation.result import result as build
    return build(job,body,files,execution,fault)
