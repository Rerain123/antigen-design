"""A1 section 7 package inventory fallback and lossless batch coverage.

All native peptide rows remain in the child artifacts. The parent stores the
residue sufficient statistics used by S-19, never a hand-picked allele subset.
"""
import math
import base64

from ...common import decode, encode, ensure, sha
from ...files import no_links, read_locked
from . import policy

MODE = 'package_pan_allele'


def manifest():
    receipt = policy.asset_receipt()
    support_raw=read_locked(no_links(policy.HERE/'pan-support.json'),65536)
    support=decode(support_raw)
    ensure(support['source_image_id']==receipt['image_id'], 'HASH_MISMATCH', 'Pan support image differs')
    channels = {}
    for kind in ('mhc_i', 'mhc_ii'):
        component = receipt['components'][kind]
        path = component['allele_inventory_path']
        raw = read_locked(no_links(policy.PACKAGE / path), 1024 * 1024)
        expected = next(row['sha256'] for row in receipt['files'] if row['path'] == path)
        ensure(sha(raw) == expected, 'HASH_MISMATCH', 'Pan inventory differs from the pinned package')
        names = [line.split()[0] for line in raw.decode('ascii').splitlines()]
        ensure(len(set(names)) == len(names) and all(policy.ALLELE.fullmatch(n) for n in names),
               'HASH_MISMATCH', 'Invalid or duplicate pan inventory names')
        availability=support['channels'][kind];excluded=availability['excluded_alleles']
        ensure(availability['inventory_sha256']==expected
               and availability['archive_sha256']==receipt['archive_sha256'][kind]
               and availability['declared_count']==len(names)
               and set(excluded)<=set(names) and len(set(excluded))==len(excluded),
               'HASH_MISMATCH', 'Pan executable support receipt differs from package')
        names=[n for n in names if n not in excluded]
        ensure(len(names)==availability['executable_count'], 'HASH_MISMATCH', 'Pan executable count differs')
        channels[kind] = dict(alleles=names, count=len(names), inventory_path=path,
                              inventory_sha256=expected, version=component['observed_version'],
                              availability=availability)
    value = dict(mode=MODE, source='ToolSpec_A1_v10.5_section_7', channels=channels,
                 package_support_sha256=sha(support_raw))
    return dict(value, sha256=sha(encode(value)))


def options(timeout_seconds=28800):
    return dict(panel_mode=MODE, panel_manifest_sha256=manifest()['sha256'], timeout_seconds=timeout_seconds)


def batches(sequence, panel):
    limits = {}
    for kind, lengths, limit in [('mhc_i', policy.MHC_I_LENGTHS, 20), ('mhc_ii', policy.MHC_II_LENGTHS, 15)]:
        rows = sum(max(0, len(sequence)-n+1) for n in lengths)
        limits[kind] = min(limit, policy.MAX_CHANNEL_ROWS // max(rows, 1))
        ensure(limits[kind] > 0, 'INVALID_REQUEST', 'One allele exceeds the native output envelope')
    count = max(math.ceil(panel['channels'][k]['count']/limits[k]) for k in limits)
    # Both native channels run in each batch; balanced partitions avoid repeated
    # alleles while retaining the existing single-call request contract.
    ensure(count > 0 and count <= min(panel['channels'][k]['count'] for k in limits if panel['channels'][k]['count']),
           'INVALID_REQUEST', 'Panel cannot be partitioned into nonempty native channel batches')
    return [dict(index=i, **{k+'_alleles': panel['channels'][k]['alleles'][
        i*panel['channels'][k]['count']//count:(i+1)*panel['channels'][k]['count']//count]
        for k in limits}) for i in range(count)]


def aggregate(sequence, panel, batch_results):
    """Validate exact request coverage, retaining missing channels as unavailable."""
    plan = batches(sequence, panel)
    results = iter(batch_results)
    state = {kind: dict(rank=[None]*len(sequence), sb=[set() for _ in sequence],
                       binders=[set() for _ in sequence], complete=bool(panel['channels'][kind]['count']), observed_rows=0,
                       skipped_inverted_rows=0) for kind in ('mhc_i', 'mhc_ii')}
    refs = []
    for expected in plan:
        entry = next(results, None)
        ensure(entry is not None, 'OUTPUT_INVALID', 'Pan batch coverage is incomplete')
        request, result, ref = entry
        ensure(request['protein_sequence'] == sequence and all(
            request[k+'_alleles'] == expected[k+'_alleles'] for k in state),
            'OUTPUT_INVALID', 'Pan batch request differs from its exact partition')
        ensure(result['binding']['sequence_sha256'] == sha(sequence.encode())
               and result.get('panel_selection', {}).get('mode') == 'explicit_alleles',
               'OUTPUT_INVALID', 'Pan child result identity or mode differs')
        refs.append(dict(index=expected['index'], artifact=ref))
        for kind, acc in state.items():
            channel = result['channels'].get(kind)
            if channel is None or channel['status'] != 'parsed_unreviewed':
                acc['complete'] = False
                continue
            lengths = policy.MHC_I_LENGTHS if kind == 'mhc_i' else policy.MHC_II_LENGTHS
            grid = len(expected[kind+'_alleles'])*sum(max(0,len(sequence)-n+1) for n in lengths)
            ensure(channel['observed_rows'] == grid and len(channel['hits']) + channel['skipped_inverted_rows'] == grid,
                   'OUTPUT_INVALID', 'Pan child native grid is incomplete')
            allowed = policy.native_output_alleles(kind, expected[kind+'_alleles'])
            acc['observed_rows'] += grid
            acc['skipped_inverted_rows'] += channel['skipped_inverted_rows']
            for hit in channel['hits']:
                start,end,rank = hit['start'],hit['end'],hit['percent_rank']
                ensure(1 <= start <= end <= len(sequence) and sequence[start-1:end] == hit['peptide_seq']
                       and hit['allele'] in allowed and math.isfinite(rank) and 0 <= rank <= 100
                       and hit['classification'] in ('SB','WB','NB'), 'OUTPUT_INVALID', 'Invalid pan peptide row')
                for offset in range(start-1,end):
                    prior = acc['rank'][offset]
                    acc['rank'][offset] = rank if prior is None else min(prior,rank)
                    if hit['classification'] == 'SB': acc['sb'][offset].add(hit['allele'])
                    if hit['classification'] in ('SB','WB'): acc['binders'][offset].add(hit['allele'])
    ensure(next(results, None) is None, 'OUTPUT_INVALID', 'Unexpected extra pan batch')
    channels = {}
    for kind, acc in state.items():
        names=sorted(set().union(*acc['sb']))
        index={name:i for i,name in enumerate(names)};width=(len(names)+7)//8
        encoded=[base64.b64encode(sum(1<<index[n] for n in alleles).to_bytes(width,'little')).decode('ascii')
                 for alleles in acc['sb']]
        channels[kind] = dict(status='parsed_unreviewed' if acc['complete'] else 'unavailable',
            hits=None, hits_storage='REGISTERED_BATCH_ARTIFACTS',
            observed_rows=acc['observed_rows'] if panel['channels'][kind]['count'] else None,
            assessment_status='PREDICTED_UNREVIEWED' if acc['complete'] else 'NOT_ASSESSED',
            skipped_inverted_rows=acc['skipped_inverted_rows'],
            residue_summary=dict(min_percent_rank=acc['rank'], sb_allele_dictionary=names,sb_bits_base64=encoded,
                                 has_binding=[bool(s) for s in acc['binders']]) if acc['complete'] else None)
    return channels, refs


def summary_sb(summary,length):
    names=summary['sb_allele_dictionary'];rows=summary['sb_bits_base64']
    ensure(names==sorted(set(names)) and len(rows)==length and len(summary['has_binding'])==length,
           'OUTPUT_INVALID','Invalid compact pan summary')
    width=(len(names)+7)//8
    for row in rows:
        raw=base64.b64decode(row,validate=True)
        value=int.from_bytes(raw,'little')
        ensure(len(raw)==width and value.bit_length()<=len(names),'OUTPUT_INVALID','Pan allele bits exceed dictionary')
        yield {name for i,name in enumerate(names) if (value>>i)&1}
