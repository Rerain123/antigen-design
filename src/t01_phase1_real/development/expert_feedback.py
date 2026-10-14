"""Immutable 2026-10-09 expert handoff; later code never edits these originals."""
from pathlib import Path

from ..common import decode, ensure, sha

ROOT = Path(__file__).parent/'assets/expert-feedback-20261009'
RECEIPT_SHA256 = '0b4df758934d408a919b5865a59a7919f65f9b6273da28afc6f337bfee43b622'
VERSION = 'expert-feedback-20261009-v1'


def authority():
    raw = (ROOT/'receipt.json').read_bytes()
    ensure(sha(raw) == RECEIPT_SHA256, 'HASH_MISMATCH', 'Expert handoff receipt changed')
    receipt = decode(raw)
    for name, item in receipt['files'].items():
        data = (ROOT/name).read_bytes()
        ensure(sha(data) == item['sha256'] and len(data) == item['bytes'],
               'HASH_MISMATCH', 'Expert handoff original changed: '+name)
    return dict(version=VERSION, receipt_sha256=RECEIPT_SHA256,
                handoff_sha256=receipt['files']['handoff.md']['sha256'])


def functional_regions(rows):
    """S27, S28 proximity and L3 exclude chain extent; N09/S45 keep it."""
    return [r for r in rows if r['type'] != 'mature_chain']
