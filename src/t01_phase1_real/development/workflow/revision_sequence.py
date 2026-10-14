"""Expert v2 §10.2: existing S-36a observations before structure allocation.

These are observations, not a new hard threshold or a final ranking score.
Only the pure sequence calculation is cached; candidate/source bindings are
rebuilt from verified generation records on every replay.
"""
from copy import deepcopy
from functools import lru_cache

from ...common import ensure, sha
from .revision_contract import IDENTITY, finite

VERSION = 'prestructure-S36a-v1'
FIELDS = ('mw_kda', 'pi', 'gravy', 'instability_index', 'aliphatic_index', 'score')


@lru_cache(maxsize=512)
def _metrics(sequence):
    from ..developability.compute import expressibility
    value = expressibility(sequence)
    ensure(value.get('status') == 'computed_unreviewed'
           and all(finite(value.get(k)) for k in FIELDS),
           'OUTPUT_INVALID', 'Prestructure sequence metrics incomplete')
    return value


def observation(record):
    ensure(record['content_hash'] == sha(record['sequence'].encode()),
           'OUTPUT_INVALID', 'Prestructure sequence identity differs')
    return dict(policy_version=VERSION, stage_id='PRE_STRUCTURE',
                execution_status='SUCCEEDED', qualification='DEVELOPMENT_UNREVIEWED',
                binding={k: record[k] for k in IDENTITY},
                generation_source=deepcopy(record['generation_source']),
                expressibility=deepcopy(_metrics(record['sequence'])),
                threshold_applied=False, ranking_role='OBSERVATION_ONLY')


def attach(records):
    for record in records:
        if record['disposition'] == 'FORMAL_POOL':
            value = observation(record)
            old = record.get('sequence_developability')
            ensure(old is None or old == value, 'OUTPUT_INVALID',
                   'Prestructure sequence metrics or binding changed')
            record['sequence_developability'] = value


def ready(record):
    value = record.get('sequence_developability')
    if value is None:
        return False
    ensure(value == observation(record), 'OUTPUT_INVALID',
           'Prestructure sequence metrics or binding changed')
    return True
