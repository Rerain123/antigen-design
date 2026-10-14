"""WT-bound proposal statistics, formal resampling masks and early hard checks.

Expert revision 2026-09-29 sections 2–6. All transformations are backend
operations; proposal sequence editing is never a formal generation method.
"""
from collections import Counter, defaultdict
from decimal import Decimal
import copy
from ...common import encode, ensure, sha
from .revision_contract import budget, check, config, diagnostic, finite, RULE

AA='ACDEFGHIKLMNPQRSTVWY'


def snapshot(wt, permissions, conversion, structure_ref, cfg, low_positions=()):
    config(cfg)
    rows=permissions['per_residue']
    ensure([r['position'] for r in rows]==list(range(1,len(wt)+1)), 'OUTPUT_INVALID','Incomplete permission snapshot')
    mapped={r['sequence_position']:r for r in conversion['rows'] if r['designed_chain']}
    ensure(set(mapped)==set(range(1,len(wt)+1)) and len(mapped)==len(wt),
           'OUTPUT_INVALID','input_or_mapping_error')
    ensure(conversion['chain_sequences'][conversion['target_chain']]==wt,
           'OUTPUT_INVALID','WT backbone sequence differs')
    low=set(low_positions)
    ensure(all(type(p) is int and 1<=p<=len(wt) for p in low),'OUTPUT_INVALID','Invalid low confidence coordinates')
    records=[];eligible=[];temporary=[]
    for row in rows:
        p=row['position'];allowed=row['allowed_residues'];address=mapped[p]
        ensure(row['wt_residue']==wt[p-1]==address['residue'] and wt[p-1] in allowed and set(allowed)<=set(AA)
               and row['design_permission'] in ('FIXED','RESTRICTED','OPEN'), 'OUTPUT_INVALID','Permission/WT mismatch')
        ensure(address['tool_position']==p and address['chain_id']==conversion['target_chain'],
               'OUTPUT_INVALID','constraint_encoding_error')
        if row['design_permission']=='FIXED':ensure(allowed==wt[p-1],'OUTPUT_INVALID','FIXED allow-set differs')
        if row['design_permission']!='FIXED' and set(allowed)-{wt[p-1]} and p not in low:eligible.append(p)
        if p in low:temporary.append(dict(position=p,reason_codes=['LOCAL_LOW_CONFIDENCE']))
        allowed_hash=sha(encode(dict(allowed_residues=allowed)))
        records.append(dict(position=p,wt_residue=wt[p-1],design_permission=row['design_permission'],
            allowed_residues=allowed,position_key=dict(reference_id=sha(wt.encode()),mapping_version=sha(encode(conversion)),
                sequence_position=p,chain_id=address['chain_id'],author_resseq=address['author_resseq'],
                insertion_code=address['insertion_code'],tool_position=address['tool_position']),
            allowed_set_ref=dict(artifact_id='allowed-'+allowed_hash,content_hash=allowed_hash,rule_version=cfg['rule_version']),
            evidence_refs=copy.deepcopy(row.get('evidence_source',[]))))
        from .revision_v2 import enabled
        if enabled(cfg):records[-1]['constraint_state']=row.get('constraint_state')
    out=dict(original_wt_seq=wt,reference_id=sha(wt.encode()),wt_structure_id=structure_ref,
        design_chain_id=conversion['target_chain'],mapping_version=sha(encode(conversion)),records=records,
        rule_version=cfg['rule_version'],calculation_config_id=cfg['calculation_config_id'],eligible_positions=eligible,
        sampling_fixed=temporary,nonstandard=permissions.get('non_standard',False))
    out['permission_snapshot_id']='permission-'+sha(encode(out))
    out['mutation_budget']=budget(wt,cfg,eligible)
    return out


def constraints(snap, opened):
    ensure(set(opened)<=set(snap['eligible_positions']),'OUTPUT_INVALID','Sampling cannot widen biological permissions')
    fixed=[];restricted=[];opened_set=set(opened);free=[]
    for r in snap['records']:
        if r['position'] not in opened_set:fixed.append(r['position'])
        elif r['design_permission']=='OPEN':free.append(r['position'])
        else:restricted.append(dict(position=r['position'],allowed_residues=r['allowed_residues']))
    return dict(purpose='ENGINEERING_EXPLICIT_MASKS',source_id=snap['permission_snapshot_id'],
                fixed_positions=fixed,restricted_positions=restricted,open_positions=free)


def inspect(snap, sequence, opened=None, *, proposal=False, scales=None):
    wt=snap['original_wt_seq'];violations=[];mutations=[]
    if not isinstance(sequence,str) or len(sequence)!=len(wt) or not set(sequence)<=set(AA):
        return check('FAIL','INVALID_SEQUENCE',mutations=[],mutation_count=None,violations=['INVALID_SEQUENCE'])
    for row,(a,b) in zip(snap['records'],zip(wt,sequence)):
        p=row['position']
        if a==b:continue
        mutations.append(dict(position=p,wt=a,mut=b))
        if b not in row['allowed_residues']:violations.append(dict(position=p,reason='PERMISSION_VIOLATION'))
        if opened is not None and p not in opened:violations.append(dict(position=p,reason='SAMPLING_FIXED_CHANGED'))
    if not proposal and len(mutations)>snap['mutation_budget']['B']:
        violations.append(dict(reason='MUTATION_BUDGET_EXCEEDED'))
    chemical=[]
    if scales is not None and not proposal:
        for m in mutations:
            delta={k:float(abs(Decimal(str(scales[k][m['wt']]))-Decimal(str(scales[k][m['mut']]))))
                   for k in ('hydrophobicity','volume','charge')}
            exceeded=[k for k,limit in dict(hydrophobicity=4.5,volume=100.,charge=1.).items() if delta[k]>limit]
            chemical.append(dict(**m,**delta,polarity_flip=(m['wt'] in scales['polar'])!=(m['mut'] in scales['polar']),exceeded=exceeded))
            if exceeded:violations.append(dict(position=m['position'],reason='CHEMICAL_HARD_FAIL',dimensions=exceeded))
    return check('FAIL' if violations else 'PASS',*sorted({r['reason'] for r in violations}),
        mutations=mutations,mutation_count=len(mutations),mutation_fraction=len(mutations)/len(wt),
        violations=violations,per_mutation_chemical=chemical)


def proposals(snap, receipts, cfg):
    """Independent repeated sequences count; repeated/conflicting draws do not."""
    groups=defaultdict(list);excluded=[];quarantine=[];valid=[]
    for receipt in receipts:
        ensure(receipt.get('receipt_id'),'OUTPUT_INVALID','Receipt audit identity required')
        row=copy.deepcopy(receipt)
        row['validity_status']='UNKNOWN'
        if row.get('sequence') is not None:
            result=inspect(snap,row['sequence'],snap['eligible_positions'],proposal=True)
            row['validity_status']='VALID' if result['check_status']=='PASS' else 'INVALID'
            row['reason_codes']=result['reason_codes']
        if row.get('source_kind')=='reference_record':excluded.append(row);continue
        if (row.get('source_kind')!='sampling_draw' or not row.get('draw_id') or not row.get('batch_id')
            or not row.get('execution_ref') or row.get('seed') not in cfg['random_seeds']
            or row.get('condition_hash')!=sha(encode(snap))):
            quarantine.append(dict(row,diagnostic=diagnostic('ASSOCIATION','association_error')));continue
        groups[row['draw_id']].append(row)
    replays=[]
    for group in groups.values():
        signatures={sha(encode({k:r.get(k) for k in ('sequence','batch_id','seed','execution_ref','condition_hash')})) for r in group}
        if len(signatures)!=1:
            quarantine.extend(dict(r,diagnostic=diagnostic('ASSOCIATION','association_error')) for r in group);continue
        row=group[0];replays.extend(group[1:])
        (valid if row['validity_status']=='VALID' else excluded).append(row)
    def stats(rows):
        n=len(rows);counts={p:Counter(r['sequence'][p-1] for r in rows) for p in snap['eligible_positions']}
        frequencies={str(p):dict(mutation_frequency=(sum(v for aa,v in c.items() if aa!=snap['original_wt_seq'][p-1])/n if n else None),
            substitutions={a:v/n for a,v in sorted(c.items())} if n else None) for p,c in counts.items()}
        order=[p for p in snap['eligible_positions'] if n and frequencies[str(p)]['mutation_frequency']>0]
        # Hash-based seeded tie breaking is independent of input receipt order.
        order.sort(key=lambda p:(-frequencies[str(p)]['mutation_frequency'],sha(f'{cfg["nomination_seed"]}:{p}'.encode())))
        nomination=order[:snap['mutation_budget']['K']]
        unique=len({r['sequence'] for r in rows})
        return dict(valid_count=n,unique_sequences=unique,duplicate_rate=1-unique/n if n else None,
            frequencies=frequencies if n else None,nomination_positions=nomination,
            tied_frequencies=len({frequencies[str(p)]['mutation_frequency'] for p in order})<len(order))
    combined=stats(valid);batches={str(seed):stats([r for r in valid if r['seed']==seed]) for seed in cfg['random_seeds']}
    for seed in cfg['random_seeds']:
        batch=batches[str(seed)]
        batch.update(requested=cfg['presampling_n']//cfg['presampling_batches'],
            invalid_count=sum(r.get('seed')==seed and r['validity_status']=='INVALID' for r in excluded),
            quarantined_count=sum(r.get('seed')==seed for r in quarantine),
            replayed_count=sum(r.get('seed')==seed for r in replays))
    sets=[set(b['nomination_positions']) for b in batches.values()]
    return dict(stage='proposal_only',**combined,batches=batches,batch_nomination_overlap=sorted(set.intersection(*sets)),
        receipts=receipts,valid_receipts=valid,excluded_receipts=excluded,quarantine_receipts=quarantine,replayed_receipts=replays,
        reason_codes=[] if valid else ['no_valid_presampling'],condition_hash=sha(encode(snap)))


def formal(snap, generated, nomination, cfg, previous, source):
    known={r['content_hash']:r['candidate_id'] for r in previous};out=[]
    for record in generated:
        seq=record['sequence'];digest=sha(seq.encode());verdict=inspect(snap,seq,set(nomination),scales=source['scales'])
        cid='candidate-'+digest
        row=dict(candidate_id=cid,content_hash=digest,reference_id=snap['reference_id'],sequence=seq,
            calculation_config_id=cfg['calculation_config_id'],rule_version=cfg['rule_version'],stage='formal',
            sample_number=record['sample_number'],generation_source=source['generation_ref'],
            permission_snapshot_id=snap['permission_snapshot_id'],constraint_check=verdict,
            mutations=verdict['mutations'],nonstandard=snap['nonstandard'],duplicate_of=known.get(digest),
            disposition='REJECTED' if verdict['check_status']=='FAIL' else 'WT_CONTROL' if seq==snap['original_wt_seq']
                        else 'DUPLICATE' if digest in known else 'FORMAL_POOL')
        known.setdefault(digest,cid);out.append(row)
    return out


def select_structure(records, scored, remaining, *, require_sequence_metrics=False):
    ensure(type(remaining) is int and remaining>=0,'OUTPUT_INVALID','Invalid remaining structure budget')
    eligible=[]
    for row in records:
        score=scored.get(row['candidate_id'],{})
        if row['disposition']=='FORMAL_POOL' and score.get('check_status')=='PASS' and finite(score.get('score')):
            if require_sequence_metrics:
                from .revision_sequence import ready
                if not ready(row):continue
            eligible.append(row)
    eligible.sort(key=lambda r:(-scored[r['candidate_id']]['score'],len(r['mutations']),r['candidate_id']))
    return [r['candidate_id'] for r in eligible[:remaining]]


def esm_check(score, baseline, near_zero):
    if not finite(score) or not finite(baseline):return check('NOT_ASSESSED','ESM_SCORE_UNAVAILABLE',score=score,baseline=baseline)
    if near_zero is None or not finite(near_zero) or near_zero<0:
        return check('NOT_ASSESSED','configuration_incomplete',score=score,baseline=baseline,
                     diagnostic=diagnostic('CONFIGURATION','configuration_incomplete','ESM near-zero policy'))
    if baseline>=0 or abs(baseline)<=near_zero:return check('NOT_ASSESSED','INVALID_BASELINE',score=score,baseline=baseline)
    delta=(Decimal(str(score))-Decimal(str(baseline)))/abs(Decimal(str(baseline)))
    return check('PASS' if delta>=Decimal('-.10') else 'FAIL',score=score,baseline=baseline,
                 delta_pct=float(delta*100),evaluation_profile_id='original')
