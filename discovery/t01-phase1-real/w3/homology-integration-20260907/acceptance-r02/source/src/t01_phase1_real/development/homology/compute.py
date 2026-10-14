"""Source-bound S-13/14/15 calculations; shared by worker and receipt validation.

No network, tool invocation, or scientific qualification is performed here.
Coordinates are explicitly mapped from MSA columns to the query anchor.
"""
from collections import Counter, defaultdict
import math
import re

AA = frozenset('ACDEFGHIKLMNPQRSTVWY')
ANCHOR = 't01_n08_query_anchor'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fasta(raw, aligned=False):
    rows = {}
    current = None
    for line in raw.splitlines():
        if line.startswith('>'):
            current = line[1:].split()[0]
            require(re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', current) and current not in rows,
                    'Duplicate or unsafe FASTA ID')
            rows[current] = ''
        elif line.strip():
            require(current is not None, 'Sequence before FASTA header')
            rows[current] += line.strip().upper() if aligned else line.strip()
    require(rows and all(s and set(s) <= (AA | {'-'} if aligned else AA) for s in rows.values()),
            'Empty or invalid FASTA sequence')
    if aligned:
        require(len({len(s) for s in rows.values()}) == 1, 'Unequal MSA lengths')
    return rows


def format_fasta(rows):
    return ''.join('>' + key + '\n' + value + '\n' for key, value in rows.items())


def annotation_groups(records, group_by):
    subtypes, hosts = defaultdict(list), defaultdict(list)
    missing_subtype = missing_host = 0
    for item in records:
        label = next((item.get(k) for k in ('serotype', 'subtype', 'genotype') if item.get(k)), None)
        if label is None:
            match = re.search(r'\b(?:serotype|subtype|genotype|type)\s+([A-Za-z0-9_.-]+)', item['header'], re.I)
            label = match.group(1) if match else None
        if label is None:
            missing_subtype += 1
            # Literal S-13 assignment is retained as metadata. Ambiguous unknown
            # grouping is deliberately withheld below, never guessed from sequence.
            label = 'unknown_' + item['id'][:8]
        subtypes[label].append(item['id'])
        host = item.get('host_species')
        if host is None:
            match = re.search(r'\bhost=([^;|]+)', item['header'], re.I)
            host = match.group(1).strip() if match else None
        if not host:
            missing_host += 1
            host = 'unknown'
        hosts[host].append(item['id'])
    total = len(records)
    stats = lambda n: dict(parsed=total-n, unknown=n, total=total, missing_rate=n/total if total else None)
    return dict(subtype_groups=dict(subtypes), host_groups=dict(hosts),
                subtype_parse_stats=stats(missing_subtype), host_parse_stats=stats(missing_host))


def conservation(msa, ids, query):
    require(ids and len(set(ids)) == len(ids) and all(i in msa for i in ids), 'Invalid MSA analysis members')
    anchor = msa[ANCHOR]
    require(anchor.replace('-', '') == query, 'MSA query sequence changed')
    entropy, scores, classes, unreliable, mapping, all_gap = [], [], [], [], [], []
    position = 0
    for col, residue in enumerate(anchor, 1):
        if residue != '-':
            position += 1
        mapping.append(position if residue != '-' else None)
        counts = Counter(msa[key][col-1] for key in ids)
        gaps = counts.pop('-', 0)
        if gaps / len(ids) > .5:
            unreliable.append(col)
        n = sum(counts.values())
        if n == 0:
            entropy.append(None); scores.append(None); classes.append(None); all_gap.append(col)
        else:
            h = -sum((count/n)*math.log2(count/n) for count in counts.values())
            score = 1-h/math.log2(20)
            entropy.append(h); scores.append(score)
            classes.append('highly' if score >= .93 else 'moderate' if score >= .80 else 'variable')
    query_columns = [i for i, p in enumerate(mapping) if p is not None]
    return dict(entropy=entropy, score=scores, **{'class':classes},
                unreliable_positions=unreliable, all_gap_positions=all_gap,
                msa_column_to_query_position=mapping, query_position_to_msa_column=[i+1 for i in query_columns],
                score_per_residue=[scores[i] for i in query_columns],
                entropy_per_residue=[entropy[i] for i in query_columns],
                class_per_residue=[classes[i] for i in query_columns],
                unreliable_query_positions=[mapping[i-1] for i in unreliable if mapping[i-1] is not None],
                analysis_sequence_ids=ids, query_anchor_counted=False,
                coordinate_base=1, msa_reused=True)


def confidence(records, groups, conservation_value, group_by, qualification):
    n = len(records)
    gap = len(conservation_value['unreliable_positions']) / len(conservation_value['score'])
    known_subtypes = sum(not name.startswith('unknown_') for name in groups['subtype_groups'])
    known_hosts = sum(name != 'unknown' for name in groups['host_groups'])
    # Unknown IDs do not manufacture independent biological lineages.
    coverage = (known_subtypes if group_by == 'subtype' else known_hosts if group_by == 'host_species'
                else max(known_subtypes, known_hosts)) or 1
    base = 'LOW' if n < 10 or gap > .5 else 'HIGH' if n >= 20 and gap < .1 and coverage >= 3 else 'MEDIUM'
    independent = {r['independent_stratum'] for r in records if r.get('independent_stratum')}
    verified_stratification = qualification != 'ENGINEERING_FIXTURE' and len(independent) >= 3
    final = base if verified_stratification else {'HIGH':'MEDIUM', 'MEDIUM':'LOW', 'LOW':'LOW'}[base]
    return dict(N_eff=n, gap_fraction=gap, lineage_coverage=coverage,
                base_confidence=base, conservation_confidence=final,
                independent_strata_count=len(independent), stratification_supported=verified_stratification,
                downgrade_reason=None if verified_stratification else 'INDEPENDENT_STRATIFICATION_NOT_ESTABLISHED')


def runs(scores, threshold):
    intervals = []
    start = None
    for i, score in enumerate(scores + [None], 1):
        if score is not None and score >= threshold:
            if start is None: start = i
        elif start is not None:
            intervals.append((start, i-1)); start = None
    return intervals


def regions(conservation_value, subtype_names=(), query_range=None):
    scores = conservation_value['score_per_residue']
    if query_range is not None:
        start, end = query_range
        selected = scores[start-1:end]
        uncertain = any(x is None for x in selected) or any(start <= p <= end for p in conservation_value['unreliable_query_positions'])
        return dict(status='review_required' if uncertain else 'range_statistics', regions=None, fixed_positions=None,
                    quality_flag=None, relaxation_history=[], query_range=query_range,
                    statistics=None if uncertain else dict(mean=sum(selected)/len(selected), min=min(selected), max=max(selected),
                        **{'class':'highly' if sum(selected)/len(selected)>=.93 else 'moderate' if sum(selected)/len(selected)>=.80 else 'variable'}),
                    review_reasons=['UNRELIABLE_QUERY_RANGE'] if uncertain else [])
    # S-14 marks these positions unreliable but S-15 does not specify their use.
    # Keep numerical observations; do not turn untrustworthy columns into constraints.
    if any(x is None for x in scores) or conservation_value['unreliable_query_positions']:
        return dict(status='review_required', regions=None, fixed_positions=None, quality_flag=None,
                    relaxation_history=[], review_reasons=['UNRELIABLE_POSITION_REGION_POLICY_UNRESOLVED'])
    history, attempts = [], []
    for threshold, length, quality in ((.90,15,'standard'),(.70,10,'relaxed'),(.50,8,'minimal')):
        intervals = runs(scores, threshold)
        # The original does not say whether bridging below-threshold gaps can
        # violate the tier's continuous-score requirement. Only that case closes.
        ambiguous = any(c-b-1 <= 3 and (b-a+1 < 8 or d-c+1 < 8)
                        for (a,b),(c,d) in zip(intervals, intervals[1:]))
        attempts.append(dict(min_conservation=threshold, min_length=length, quality_flag=quality))
        history.append(dict(step='extract_conserved_regions', parameter='min_conservation',
                            original_value=.90, relaxed_value=threshold, quality_flag=quality))
        if quality != 'standard':
            history.append(dict(step='extract_conserved_regions', parameter='min_length',
                                original_value=15, relaxed_value=length, quality_flag=quality))
        if ambiguous:
            return dict(status='review_required', regions=None, fixed_positions=None, quality_flag=None,
                        relaxation_history=history, attempted_tiers=attempts,
                        review_reasons=['SHORT_FRAGMENT_BRIDGE_ORDER_UNRESOLVED'])
        selected = [dict(start=a,end=b,length=b-a+1,mean_conservation=sum(scores[a-1:b])/(b-a+1),
                         subtypes_covered=list(subtype_names),quality_flag=quality) for a,b in intervals if b-a+1 >= length]
        if selected:
            return dict(status='regions_unreviewed', regions=selected,
                        fixed_positions=[i for r in selected for i in range(r['start'],r['end']+1)],
                        quality_flag=quality, relaxation_history=history, attempted_tiers=attempts, review_reasons=[])
    return dict(status='no_conserved_region',regions=[],fixed_positions=[],quality_flag='failed',
                relaxation_history=history,attempted_tiers=attempts,review_reasons=[])


def analyze(msa, records, body, qualification):
    require(len({len(row) for row in msa.values()}) == 1, 'Unequal MSA lengths')
    ids = [r['id'] for r in records]
    require(set(msa) == set(ids) | {ANCHOR}, 'MSA inventory differs')
    require(all(msa[r['id']].replace('-', '') == r['sequence'] for r in records), 'MSA homolog sequence changed')
    groups = annotation_groups(records, body['group_by'])
    global_value = conservation(msa, ids, body['protein_sequence'])
    conf = confidence(records, groups, global_value, body['group_by'], qualification)
    global_value.update(conservation_confidence=conf['conservation_confidence'], msa_path='output/global.msa.fasta')
    analyses = {}
    for dimension in ('subtype', 'host'):
        if dimension == 'host' and body['group_by'] == 'subtype': continue
        # Always preserve subtype separation, even in a host-only request.
        for name, members in groups[dimension+'_groups'].items():
            key = dimension + ':' + name
            if dimension == 'subtype' and name.startswith('unknown_'):
                analyses[key] = dict(status='review_required',sequence_ids=members,conservation=None,
                                     regions=None,reason='UNKNOWN_SUBTYPE_GROUPING_UNRESOLVED')
                continue
            value = conservation(msa, members, body['protein_sequence'])
            value.update(conservation_confidence=conf['conservation_confidence'],msa_path='output/global.msa.fasta')
            analyses[key] = dict(status='computed_unreviewed',sequence_ids=members,conservation=value,
                                 regions=regions(value,[name] if dimension=='subtype' else [],body['query_range']))
    if body['group_by'] == 'both':
        for subtype, members in groups['subtype_groups'].items():
            if subtype.startswith('unknown_'): continue
            for host, host_ids in groups['host_groups'].items():
                subset = [key for key in members if key in host_ids]
                if subset:
                    value = conservation(msa,subset,body['protein_sequence'])
                    value.update(conservation_confidence=conf['conservation_confidence'],msa_path='output/global.msa.fasta')
                    analyses['both:'+subtype+':'+host] = dict(status='computed_unreviewed',sequence_ids=subset,
                        conservation=value,regions=regions(value,[subtype],body['query_range']))
    # Mixed subtype global observations remain diagnostics; no pooled constraints
    # silently replace required independent subtype results (SOP T-01 step9).
    pooled_allowed = len(groups['subtype_groups']) == 1 and not groups['subtype_parse_stats']['unknown']
    extracted = regions(global_value,list(groups['subtype_groups']),body['query_range']) if pooled_allowed else dict(
        status='review_required',regions=None,fixed_positions=None,quality_flag=None,relaxation_history=[],
        review_reasons=['SUBTYPE_SELECTION_OR_UNKNOWN_GROUPING_REQUIRES_REVIEW'])
    return dict(groups=groups,confidence=conf,conservation=global_value,region_extraction=extracted,
                group_analyses=analyses,global_conservation_role='diagnostic' if not pooled_allowed else 'single_subtype',
                msa_alignment_count=1,scientific_consumption=False)
