"""Prepare sourced benign inputs and declared checks; no inference or scientific outputs."""
import ast
import hashlib
import json
from pathlib import Path

BATCH = Path(__file__).resolve().parent
ROOT = BATCH.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    target = BATCH/'validation'
    target.mkdir(exist_ok=False)
    notebook = BATCH/'official_sources/esm/cookbook/tutorials/esmfold2_local_gpu.ipynb'
    sequence = None
    for cell in json.loads(notebook.read_text())['cells']:
        if cell['cell_type']=='code' and 'UBIQUITIN =' in ''.join(cell['source']):
            tree = ast.parse(''.join(cell['source']))
            for node in tree.body:
                if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='UBIQUITIN' for t in node.targets):
                    sequence = ast.literal_eval(node.value)
    if not isinstance(sequence,str) or len(sequence)!=76 or not set(sequence)<=set('ACDEFGHIKLMNPQRSTVWY'):
        raise ValueError('Official ubiquitin example changed')
    prior = ROOT/'tests/fixtures/structure_mapping/real/1UBQ.fasta'
    prior_seq = ''.join(line.strip() for line in prior.read_text().splitlines() if line and not line.startswith('>'))
    if prior_seq != sequence:
        raise ValueError('Official tutorial and existing input differ')
    fasta = target/'ubiquitin76.fasta'
    fasta.write_text('>w1g0_ubiquitin76\n'+sequence+'\n')
    af3 = dict(name='w1g0_ubiquitin76',sequences=[dict(protein=dict(id='A',sequence=sequence))],modelSeeds=[1],dialect='alphafold3',version=1)
    (target/'af3_full_pipeline_input.json').write_text(json.dumps(af3,indent=2))
    cases = [
        dict(id='PRED-01',engine='AF3',input='ubiquitin76.fasta',kind='OFFICIAL_TUTORIAL_SEQUENCE',
             checks=['Original local data pipeline input: MSA/template fields unset, never silently emptied',
                     'One seed and 5 diffusion samples; save every original mmCIF and confidence JSON',
                     'Compare project monomer pTM choice with official ranking; check has_clash for selected sample',
                     'Extract C-alpha pLDDT, explicitly normalize 0-100 to 0-1; preserve 76 input positions',
                     'Record runtime/GPU/RSS/network-none, errors and all hashes']),
        dict(id='PRED-02',engine='ESMFold2',input='ubiquitin76.fasta',kind='OFFICIAL_TUTORIAL_SEQUENCE',
             checks=['Use pinned standard checkpoint, ESMC-6B and CCD; Fast is a separate candidate',
                     'Record wrapper defaults and fixed seed; no hidden performance overrides',
                     'Save mmCIF, complete raw pLDDT/pTM and all returned outputs with dtype/shape',
                     'Verify model raw API scale and exported B-factor scale separately',
                     'Resolve chain/token positions against original 76-aa input; no guessed labels',
                     'Offline missing nested backbone/CCD must fail, never fetch them during prediction']),
        dict(id='PRED-03',engine='AF3',input='authentic_precomputed_data.json',kind='NOT_YET_AVAILABLE',
             checks=['Local CPU data stage produces hash-bound MSA/templates for exact sequence',
                     'GPU inference with --run_data_pipeline=false must reuse actual data',
                     'Blank synthetic MSA/template fields are not evidence for the intended MSA pipeline']),
        dict(id='PRED-04',engine='both',input='fault_inputs',kind='SYNTHETIC_INPUT_AND_FAULT_INJECTION_PLANNED',
             checks=['Reject empty/illegal input, missing/corrupt weights and mismatched sequence output',
                     'Truncated confidence arrays, NaN/Inf, unknown scale and missing C-alpha require explicit failure/review',
                     'pTM unavailable remains null; no guessed topology reliability',
                     'Timeout/cancel only this job; preserve the actual reason']),
        dict(id='PRED-05',engine='AF3_then_ESMFold2',input='length_999_1000_1500_1501.fasta',kind='SYNTHETIC_BOUNDARY_INPUTS_NOT_MODEL_BENCHMARK',
             checks=['1000/1500/1501 branches follow original warning/fallback rules',
                     'Do not create real OOM or wait 2 hours merely to test state routing',
                     'A short development timeout must not be mislabeled the expert >2-hour scientific fallback condition',
                     'Record injected fault evidence separately from real long-sequence prediction'])]
    for case in cases:
        case['execution_status']='DECLARED_NOT_RUN'
        case['scientific_reference_status']='NOT_SIGNED_OFF'
    long_inputs = ''.join('>synthetic_length_'+str(n)+'\n'+(sequence*((n+75)//76))[:n]+'\n' for n in [999,1000,1500,1501])
    (target/'length_999_1000_1500_1501.fasta').write_text(long_inputs)
    (target/'empty.fasta').write_text('')
    (target/'illegal.fasta').write_text('>synthetic_illegal\nACDE*\n')
    plan = dict(scope='W1-04_G0_PREPARATION_ONLY',model_execution='NOT_RUN',production_status='NOT_DEPLOYED',
                input_provenance=[dict(path=notebook.relative_to(ROOT).as_posix(),sha256=sha(notebook),locator='code cell UBIQUITIN assignment'),
                                  dict(path=prior.relative_to(ROOT).as_posix(),sha256=sha(prior),role='Existing local identical-sequence cross-check; no historical query')],
                sequence_sha256=hashlib.sha256(sequence.encode()).hexdigest(),
                af3_profile=dict(source_commit='c0f97eda2f1f482fd94d3a38bece18c7069b4a5c',num_diffusion_samples=5,model_seeds=[1],
                                 data_pipeline=True,inference=True,network_mode='none',execution_status='NOT_RUN'),
                esm_profile=dict(candidate_repository='biohub/ESMFold2',candidate_revision='e1e189d0f5fb70c2693da2332eca4443c0ccccd6',
                                 code_commit='bf343ba264b650dff7a073643725f9aaa1fdbe8d',
                                 num_loops=20,num_sampling_steps=200,num_diffusion_samples=1,seed=1,lm_dropout=0.3,
                                 msa_max_depth=1024,msa_column_mask_rate=0.1,
                                 kernel_backend='Default, must record resolved backend at runtime',
                                 offline_assets=['fold checkpoint/config','ESMC-6B 6 shards/index/config','ccd.pkl'],
                                 network_mode='none',execution_status='NOT_RUN',scientific_parameter_approval='PENDING_G1'),
                cases=cases,execution_preconditions=['Suitable concrete server profile and bounded work directory',
                     'Asset identities + local SHA-256 verified; dependency image pinned',
                     'Applicable AF3 model/output terms recorded by user organization',
                     'Local database or authentic precomputed MSA/template inputs available',
                     'Actual inference remains separate from metadata/GPU-visibility checks'],
                scientific_accuracy='No accuracy estimate; public example is not independent hold-out')
    (target/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'prepared_cases':len(cases),'model_execution':'NOT_RUN','normal_input_length':len(sequence)}))


if __name__=='__main__':
    build()
