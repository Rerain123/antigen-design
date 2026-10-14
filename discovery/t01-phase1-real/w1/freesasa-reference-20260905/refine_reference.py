"""Follow-up prompted by failed 3840-to-15360 point convergence; preserve initial study."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from compare_reference import bio_areas, aggregate, compare, fingerprint

output = Path('/out/result')
output.mkdir(exist_ok=False)
spec = json.loads(Path('/refinement_spec.json').read_text())
initial = Path('/initial')
atoms = json.loads((initial/'shared_geometry.json').read_text())
timer = time.perf_counter()
areas = bio_areas([a['coordinate'] for a in atoms], [a['radius'] for a in atoms], spec['n_points'])
run = {'id':f"Biopython-SR-{spec['n_points']}", 'parameters':{'probe-radius':1.4,'n-points':spec['n_points']},
       'total_sasa_a2':sum(areas), 'atoms_sasa_a2':areas, 'residues':aggregate(areas,atoms),
       'elapsed_seconds':time.perf_counter()-timer}
(output/(run['id']+'.json')).write_text(json.dumps(run,indent=2,allow_nan=False)+'\n')
maxima=json.loads(Path('/reference_spec.json').read_text())['tien_theoretical_by_three_letter']
comparisons=[compare(json.loads((initial/(identifier+'.json')).read_text()),run,maxima)
             for identifier in ['Biopython-SR-15360','FreeSASA-LR-20','FreeSASA-LR-100','FreeSASA-LR-200','FreeSASA-LR-400']]
result={'recorded_at':datetime.now(timezone.utc).isoformat(), 'reference_spec':fingerprint('/reference_spec.json'),
        'refinement_spec':fingerprint('/refinement_spec.json'), 'probe_source':fingerprint(__file__),
        'initial_geometry':fingerprint(initial/'shared_geometry.json'), 'comparisons':comparisons,
        'network_interfaces':sorted(p.name for p in Path('/sys/class/net').iterdir()), 'production_approved':False}
(output/'comparison.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps({'reference':run['id'], 'total':run['total_sasa_a2'], 'elapsed_seconds':run['elapsed_seconds']}),flush=True)
