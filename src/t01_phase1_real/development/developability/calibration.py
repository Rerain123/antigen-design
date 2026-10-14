"""Offline C44 calibration machinery. No approved full profile exists yet.

Generic streaming moments and reproducible Swiss-Prot sampling can be verified
independently. Preparation only evaluates defined intermediate terms; it never
publishes final CamSol mu/sigma or alters the immutable expert parameters.
"""
from pathlib import Path
import math
import numpy as np
from ...common import decode,encode,ensure,sha
from .camsol import parameters,intrinsic_terms

ASSETS=Path(__file__).parent/'assets/camsol-preparation-v1'
MANIFEST_SHA='5a05a029a2179aae58e15438d7c5a2c364b24a0e6216f748249cbf9d0f4ffc0c'


def assets():
    raw=(ASSETS/'manifest.json').read_bytes()
    ensure(sha(raw)==MANIFEST_SHA,'HASH_MISMATCH','CamSol preparation manifest changed')
    m=decode(raw)
    for item in m['sources'].values():
        data=(ASSETS/item['file']).read_bytes()
        ensure(sha(data)==item['sha256'] and len(data)==item['bytes'],'HASH_MISMATCH','CamSol public source changed')
    return m


def batches(frequencies,*,seed=4401,length=200,count=100000,batch_size=256):
    aa='ACDEFGHIKLMNPQRSTVWY'
    ensure(set(frequencies)==set(aa) and all(math.isfinite(v) and v>0 for v in frequencies.values()) and
        abs(sum(frequencies.values())-1)<1e-12,'INVALID_REQUEST','Exact normalized AA20 frequencies required')
    ensure(all(type(v) is int and v>0 for v in (length,count,batch_size)) and type(seed) is int and seed>=0,
        'INVALID_REQUEST','Positive calibration dimensions and explicit nonnegative seed required')
    rng=np.random.Generator(np.random.PCG64(seed));p=[frequencies[a] for a in aa]
    for start in range(0,count,batch_size):
        yield rng.choice(20,size=(min(batch_size,count-start),length),p=p)


def moments(chunks):
    """Population moments with stable parallel-Welford combination."""
    count=0;mean=0.;m2=0.
    for chunk in chunks:
        x=np.asarray(chunk,dtype=np.float64).ravel()
        ensure(x.size>0 and np.isfinite(x).all(),'OUTPUT_INVALID','Nonfinite/empty calibration profile')
        n=x.size;avg=float(x.mean());delta=avg-mean;new=count+n
        m2+=float(np.sum((x-avg)**2))+delta*delta*count*n/new
        mean+=delta*n/new;count=new
    ensure(count>0,'INVALID_REQUEST','No calibration observations')
    return dict(count=int(count),mean=mean,population_std=math.sqrt(max(0.,m2/count)))


def calibrate(profile,frequencies,*,seed=4401,length=200,count=100000,batch_size=256):
    """Numerical engine accepts a separately specified profile, never a default guess.

    Returns unapproved diagnostic moments only. Production normalization is not
    connected to this function until OI-025 and independent reference are closed.
    """
    ensure(callable(profile),'INVALID_REQUEST','Explicit profile evaluator required')
    def chunks():
        for x in batches(frequencies,seed=seed,length=length,count=count,batch_size=batch_size):
            y=np.asarray(profile(x));ensure(y.shape==x.shape,'OUTPUT_INVALID','Calibration profile shape differs')
            yield y
    return dict(diagnostic_moments=moments(chunks()),length=length,sequence_count=count,seed=seed,
        rng='numpy.PCG64',numpy_version=np.__version__,qualification='UNAPPROVED_NUMERICAL_DIAGNOSTIC',
        mu_random=None,sigma_random=None,scientific_consumption=False)


def prepare(*,count=100000):
    m=assets();p=parameters();aa=m['amino_acid_order']
    # Independent scalar evaluator is compared against this vectorized Eq.1.
    c=p['linear_coefficients'];s=p['amino_acid_scales']
    weights=np.array([sum(c[k]*s[a][v] for k,v in (('a_H','hydrophobicity'),('a_C','charge'),
        ('a_alpha','alpha'),('a_beta','beta'))) for a in aa])
    scalar=np.array(intrinsic_terms(aa,p)['eq1_raw'])
    ensure(np.allclose(weights,scalar,rtol=0,atol=1e-12),'OUTPUT_INVALID','Independent Eq1 validation failed')
    result=calibrate(lambda x:weights[x],m['frequencies'],count=count)
    result.update(kind='C44_PREPARATION_EQ1_ONLY',manifest_sha256=MANIFEST_SHA,
        approved_profile=None,normalized_profile=None,global_score=None,
        blocked=m['blocked'],eq1_reference_max_error=float(np.max(abs(weights-scalar))),
        analytical_eq1_mean=float(sum(m['frequencies'][a]*weights[i] for i,a in enumerate(aa))))
    return result
