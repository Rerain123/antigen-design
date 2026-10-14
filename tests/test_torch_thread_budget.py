from types import SimpleNamespace

import pytest

from t01_phase1_real.development.torch_threads import resident_thread_budget


def fake_torch():
    state = dict(intra=1, inter=1)
    return SimpleNamespace(
        set_num_threads=lambda n: state.update(intra=n),
        set_num_interop_threads=lambda n: state.update(inter=n),
        get_num_threads=lambda: state['intra'], get_num_interop_threads=lambda: state['inter'])


def test_native_host_count_is_capped_and_recorded_even_on_failure():
    torch = fake_torch()
    originals = (torch.set_num_threads, torch.set_num_interop_threads)
    record = {}
    with pytest.raises(RuntimeError, match='native failure'):
        with resident_thread_budget(torch, dict(T01_RESIDENT_OFFLINE='1', OMP_NUM_THREADS='2', MKL_NUM_THREADS='4'), record):
            torch.set_num_threads(192)
            torch.set_num_interop_threads(194)
            assert (torch.get_num_threads(), torch.get_num_interop_threads()) == (2, 2)
            raise RuntimeError('native failure')
    assert (torch.set_num_threads, torch.set_num_interop_threads) == originals
    assert record['calls'] == [dict(setter='set_num_threads', requested=192, applied=2),
                               dict(setter='set_num_interop_threads', requested=194, applied=2)]


def test_historical_nonresident_execution_is_unchanged():
    torch = fake_torch()
    record = {}
    with resident_thread_budget(torch, {}, record):
        torch.set_num_threads(8)
    assert torch.get_num_threads() == 8
    assert record == {}


def test_invalid_budget_fails_before_native_execution():
    torch = fake_torch()
    with pytest.raises(ValueError):
        with resident_thread_budget(torch, dict(T01_RESIDENT_OFFLINE='1', OMP_NUM_THREADS='0', MKL_NUM_THREADS='2'), {}):
            pytest.fail('must not execute')
