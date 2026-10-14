"""Independent output checks; optimizer and validators do not share constraint evaluators."""
import csv
import io
import math
from Bio.Data import CodonTable
from Bio.Seq import Seq
from Bio.Restriction import BsaI,BpiI
from ...common import ensure
from .policy import PARAMETERS

def table(raw):
    rows=list(csv.DictReader(io.StringIO(raw.decode('ascii'))));out={};seen=set()
    reference=CodonTable.unambiguous_dna_by_id[1]
    for row in rows:
        aa=row['amino_acid'];codon=row['codon'].replace('U','T');f=float(row['relative_frequency'])
        ensure(codon not in seen and len(codon)==3 and set(codon)<=set('ACGT') and math.isfinite(f) and 0<f<=1,
            'CODON_TABLE_INVALID','Invalid or duplicate codon frequency')
        ensure(reference.forward_table.get(codon,'*')==aa,'CODON_TABLE_INVALID','Codon translation differs from standard code')
        seen.add(codon);out.setdefault(aa,{})[codon]=f
    ensure(len(seen)==64,'CODON_TABLE_INVALID','Complete 64-codon table required')
    # Kazusa bundled values are rounded to two decimals. Preserve their ratios,
    # explicitly normalize each synonymous group for the library API.
    ensure(all(abs(sum(group.values())-1)<=.031 for group in out.values()),'CODON_TABLE_INVALID','Invalid synonymous group total')
    return {aa:{c:f/sum(group.values()) for c,f in group.items()} for aa,group in out.items()}

def reverse_translate(protein,usage):
    return ''.join(sorted(usage[aa],key=lambda c:(-usage[aa][c],c))[0] for aa in protein)

def checks(dna,protein):
    ensure(isinstance(dna,str) and len(dna)==3*len(protein) and set(dna)<=set('ACGT'),'OUTPUT_INVALID','Invalid coding DNA')
    translation=str(Seq(dna).translate(table=1,cds=False,to_stop=False))
    gc_count=dna.count('G')+dna.count('C');gc=gc_count/len(dna)
    sites={}
    for enzyme in (BsaI,BpiI):
        motif=enzyme.site;reverse=str(Seq(motif).reverse_complement())
        hits=[]
        for strand,pattern in (('+',motif),('-',reverse)):
            hits.extend(dict(start=i+1,end=i+len(pattern),strand=strand) for i in range(len(dna)-len(pattern)+1) if dna[i:i+len(pattern)]==pattern)
        sites[str(enzyme)]=dict(recognition_sequence=motif,hits=hits,passed=not hits)
    # Integer comparison avoids rounding at inclusive global GC boundaries.
    gc_ok=40*len(dna)<=100*gc_count<=60*len(dna)
    violations=([] if translation==protein else ['TRANSLATION_MISMATCH'])+([] if gc_ok else ['GC_OUT_OF_RANGE'])
    violations.extend('RESTRICTION_SITE_'+name for name,v in sites.items() if not v['passed'])
    return dict(translation=translation,translation_matches=translation==protein,length_nt=len(dna),gc_count=gc_count,gc_fraction=gc,
        gc_passed=gc_ok,restriction_sites=sites,violations=violations,all_constraints_pass=not violations)

def summarize(body,observation,usage):
    protein=body['protein_sequence'];initial=reverse_translate(protein,usage)
    ensure(observation['initial_dna']==initial,'OUTPUT_INVALID','Reverse translation differs from pinned frequencies')
    initial_checks=checks(initial,protein)
    ensure(initial_checks['translation_matches'],'OUTPUT_INVALID','Initial DNA translation differs')
    status=observation['status'];optimized=observation['optimized_dna']
    ensure(observation['optimizer_invoked'] is True and observation['parameters']==PARAMETERS,'OUTPUT_INVALID','Optimizer execution/profile missing')
    ensure(status in ('OPTIMIZED_ENGINEERING','OPTIMIZATION_INCOMPLETE'),'OUTPUT_INVALID','Unknown optimization status')
    if status=='OPTIMIZED_ENGINEERING':
        ensure(observation['failure'] is None and isinstance(optimized,str),'OUTPUT_INVALID','Optimizer success is inconsistent')
        final_checks=checks(optimized,protein)
        ensure(final_checks['all_constraints_pass'],'OUTPUT_INVALID','Optimized DNA violates independent constraints')
    else:
        ensure(optimized is None and isinstance(observation['failure'],dict) and observation['failure']['code']=='NO_SOLUTION',
            'OUTPUT_INVALID','Fallback must carry the native no-solution diagnostic')
        final_checks=None
    return dict(status=status,expression_host=body['expression_host'],host_profile=body['host_profile'],
        input_kind=body['input_kind'],initial_dna=initial,optimized_dna=optimized,
        returned_dna=optimized if optimized is not None else initial,returned_kind='optimized' if optimized is not None else 'unoptimized_fallback',
        initial_checks=initial_checks,optimized_checks=final_checks,optimizer_failure=observation['failure'],
        cai_score=None,cai_reason='OI_004_CAI_METHOD_REFERENCE_AND_BOUNDARIES_UNAPPROVED',
        parameters=PARAMETERS,scientific_pass=None,requires_review=True,
        review_reasons=['INDEPENDENT_ENGINEERING_INPUT_NOT_CANDIDATE','OI_004_PRODUCTION_PARAMETERS_UNAPPROVED',
            'CAI_NOT_SCIENTIFICALLY_DEFINED']+(['OPTIMIZATION_INCOMPLETE'] if optimized is None else []))

def optimize(body,table_raw):
    import copy
    import numpy as np
    from dnachisel import DnaOptimizationProblem,EnforceTranslation,AvoidPattern,EnforceGCContent,CodonOptimize,NoSolutionError
    usage=table(table_raw);initial=reverse_translate(body['protein_sequence'],usage)
    np.random.seed(PARAMETERS['seed'])
    problem=DnaOptimizationProblem(sequence=initial,logger=None,
        constraints=[EnforceTranslation(translation=body['protein_sequence'],genetic_table='Standard',start_codon=None),
            AvoidPattern('BsaI_site'),AvoidPattern('BpiI_site'),EnforceGCContent(mini=.4,maxi=.6)],
        objectives=[CodonOptimize(codon_usage_table=copy.deepcopy(usage),method='use_best_codon')])
    problem.max_random_iters=PARAMETERS['max_random_iters']
    observation=dict(initial_dna=initial,optimized_dna=None,status='OPTIMIZATION_INCOMPLETE',failure=None,
        optimizer_invoked=True,parameters=PARAMETERS)
    try:
        problem.resolve_constraints();problem.optimize()
        observation.update(optimized_dna=problem.sequence,status='OPTIMIZED_ENGINEERING')
    except NoSolutionError as exc:
        observation['failure']=dict(code='NO_SOLUTION',type=type(exc).__name__,message=str(exc))
    observation['native_constraints']=problem.constraints_text_summary()
    observation['native_objectives']=problem.objectives_text_summary()
    summarize(body,observation,usage)
    return observation
