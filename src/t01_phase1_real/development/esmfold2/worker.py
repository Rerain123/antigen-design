"""Resident command, supervised by the existing process cancellation/timeout layer."""
import argparse
import importlib.util
import os
from pathlib import Path
import socket
import sys
from .primitives import decode, encode, ensure, sha
from . import policy
from .standard import normalize, NAMES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    body_raw = (args.input_dir / 'input.json').read_bytes()
    body = policy.request(body_raw)
    binding = decode((args.input_dir / 'binding.json').read_bytes())
    ensure(binding['input_sha256'] == sha(body_raw) and binding['execution_profile'] == policy.registered_profile(),
           'PROFILE_NOT_APPROVED', 'Bound input or worker implementation changed')
    # An inherited seccomp filter must actually refuse INET socket creation.
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            s = socket.socket(family, socket.SOCK_STREAM)
        except PermissionError:
            continue
        else:
            s.close()
            raise RuntimeError('Resident INET socket restriction is not active')
    args.output_dir.mkdir(exist_ok=False)
    request_path = args.output_dir / 'native-request.json'
    request_path.write_bytes(encode(policy.native_request(body, binding)))
    sys.path.insert(0, str(policy.HERE))
    spec = importlib.util.spec_from_file_location('esmfold2_native', policy.HERE / 'native_worker.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    native_root = args.output_dir / 'raw'
    module.run(request_path, native_root, policy.HERE / 'profile.json')
    native = {n:(native_root/n).read_bytes() for n in NAMES | {'manifest.json'}}
    for name, raw in normalize(native, body, binding).items():
        (args.output_dir/name).write_bytes(raw)
    observation = decode((args.output_dir.parent/'executor-observation.json').read_bytes())
    runtime = dict(input_sha256=sha(body_raw), binding=binding,
                   source_sha256={p.name:sha(p.read_bytes()) for p in sorted(policy.HERE.iterdir())
                                  if p.suffix in ('.py','.json')},
                   network_interfaces=observation['network_interfaces'], cpu_affinity=observation['cpu_affinity'],
                   socket_probe='INET_INET6_DENIED', python_exit_code=0)
    (args.output_dir/'runtime.json').write_bytes(encode(runtime))


if __name__ == '__main__':
    main()
