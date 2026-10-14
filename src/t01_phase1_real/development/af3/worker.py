"""Resident AF3 command supervised by the shared process cancellation layer."""
import argparse
import os
from pathlib import Path
import socket

from .primitives import decode, encode, ensure, sha
from . import policy
from .native_worker import run
from .standard import normalize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    body_raw = (args.input_dir / 'input.json').read_bytes(); body = policy.request(body_raw)
    binding = decode((args.input_dir / 'binding.json').read_bytes())
    ensure(binding['input_sha256'] == sha(body_raw) and binding['execution_profile'] == policy.registered_profile(),
           'PROFILE_NOT_APPROVED', 'Bound AF3 input or implementation changed')
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            handle = socket.socket(family, socket.SOCK_STREAM)
        except PermissionError:
            continue
        else:
            handle.close(); raise RuntimeError('Resident INET socket restriction is not active')
    args.output_dir.mkdir(exist_ok=True)
    request_path = args.output_dir / 'native-request.json'
    request_path.write_bytes(encode(policy.native_request(body,binding)))
    native_root = args.output_dir / 'raw'
    prepared = decode((args.input_dir/'msa-source.json').read_bytes()) if 'msa_source' in body else None
    run(request_path,native_root,policy.HERE/'profile.json',prepared)
    native = {path.relative_to(native_root).as_posix():path.read_bytes()
              for path in sorted(native_root.rglob('*')) if path.is_file()}
    for name,raw in normalize(native,body,binding,prepared).items():
        path = args.output_dir / name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(raw)
    observation = decode((args.output_dir.parent/'executor-observation.json').read_bytes())
    runtime = dict(input_sha256=sha(body_raw),binding=binding,
        source_sha256={path.name:sha(path.read_bytes()) for path in sorted(policy.HERE.iterdir())
                       if path.suffix in ('.py','.json')},
        network_interfaces=observation['network_interfaces'],cpu_affinity=observation['cpu_affinity'],
        socket_probe='INET_INET6_DENIED',python_exit_code=0)
    (args.output_dir/'runtime.json').write_bytes(encode(runtime))


if __name__ == '__main__':
    main()
