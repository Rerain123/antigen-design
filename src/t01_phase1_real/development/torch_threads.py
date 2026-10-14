"""Apply the resident command's CPU thread budget without editing native code."""
from contextlib import contextmanager


@contextmanager
def resident_thread_budget(torch, environment, record):
    if environment.get('T01_RESIDENT_OFFLINE') != '1':
        yield
        return
    budget = min(int(environment[name]) for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS'))
    if not 1 <= budget <= 256:
        raise ValueError('Invalid resident CPU thread budget')
    record.update(policy='resident-command-thread-cap-v1', budget=budget, calls=[])
    originals = {name: getattr(torch, name) for name in ('set_num_threads', 'set_num_interop_threads')}

    def capped(name):
        def setter(requested):
            effective = min(requested, budget)
            result = originals[name](effective)
            getter = torch.get_num_threads if name == 'set_num_threads' else torch.get_num_interop_threads
            actual = getter()
            record['calls'].append(dict(setter=name, requested=requested, applied=actual))
            if actual != effective:
                raise RuntimeError('PyTorch thread budget was not applied')
            return result
        return setter

    try:
        for name in originals:
            setattr(torch, name, capped(name))
        yield
    finally:
        for name, original in originals.items():
            setattr(torch, name, original)
