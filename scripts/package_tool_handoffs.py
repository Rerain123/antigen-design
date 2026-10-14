"""Sync/build the current handoff packages, or verify them read-only (default)."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import unquote, urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/project/phase1/handoffs'
CONTRACT = ROOT / '工作流设计/02-数据契约/tool-interface-v0.1'
PACKAGES = ('PH1-TOOL-FREESASA', 'PH1-TOOL-BEPIPRED')
EXPERT_DIRNAME = '抗原智能体_v10.5_修订版_20260902'
VERSION = '0.1'
REVISION = 'shared-interface-20260905'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def files(root):
    return sorted(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validator():
    spec = importlib.util.spec_from_file_location('portable_tool_interface', CONTRACT / 'validate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_source_copies(pkg):
    manifest = json.loads((pkg / 'references/SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
    for row in manifest['sources']:
        source, copied = (ROOT / row['source_path']).read_bytes(), (pkg / row['package_path']).read_bytes()
        require(source == copied and len(source) == row['bytes'] and digest(source) == row['sha256'],
                f"{pkg.name}: authoritative copy drift: {row['package_path']}")
    return len(manifest['sources'])


def build():
    # Preflight before any mutation. Expert copies are never rewritten by this script.
    v = validator()
    for request in (CONTRACT / 'examples').glob('*/request.json'):
        require(not v.validate_paths(request, request.parent / 'output/result.json', True), f'Invalid canonical example: {request}')
    for package in PACKAGES:
        check_source_copies(BASE / package)
    rows = []
    for package in PACKAGES:
        pkg = BASE / package
        for source in files(CONTRACT):
            target = pkg / 'interface' / source.relative_to(CONTRACT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        included = [p for p in files(pkg) if p != pkg / 'PACKAGE_MANIFEST.json']
        manifest = {'document_type': 'DEVELOPMENT_TASK_HANDOFF', 'package_id': package,
                    'version': VERSION, 'revision': REVISION, 'updated_on': '2026-09-05',
                    'contract_version': '0.1.0', 'implementation_status': 'VALIDATOR_ONLY_NO_SCIENTIFIC_ADAPTER',
                    'production_status': 'NOT_DEPLOYED', 'files': [
                        {'path': p.relative_to(pkg).as_posix(), 'bytes': p.stat().st_size, 'sha256': digest(p.read_bytes())}
                        for p in included]}
        write_json(pkg / 'PACKAGE_MANIFEST.json', manifest)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for path in files(pkg):
                info = zipfile.ZipInfo(f'{package}/{path.relative_to(pkg).as_posix()}', (2026, 9, 5, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())
        data = buffer.getvalue()
        target = BASE / 'releases' / f'{package}-v{VERSION}.zip'
        target.write_bytes(data)
        target.with_suffix('.zip.sha256').write_text(f'{digest(data)}  {target.name}\n', encoding='utf-8')
        rows.append({'package_id': package, 'version': VERSION, 'revision': REVISION,
                     'archive': target.name, 'bytes': len(data), 'sha256': digest(data), 'file_count': len(included) + 1})
    write_json(BASE / 'releases/RELEASES.json', {'document_type': 'TOOL_HANDOFF_RELEASE_INDEX',
               'updated_on': '2026-09-05', 'delivery_status': 'PACKAGED_NOT_SENT',
               'revision_policy': 'USER_REQUESTED_REPLACE_CURRENT_V0.1_NO_OLD_RELEASE', 'packages': rows})


def check():
    v = validator()
    index = v.strict_json(BASE / 'releases/RELEASES.json')
    require({r['package_id'] for r in index['packages']} == set(PACKAGES) and len(index['packages']) == 2,
            'Release package set mismatch')
    report = {'status': 'PASS', 'scope': 'handoff_archive_and_engineering_interface',
              'scientific_tool_execution': 'NOT_RUN', 'scientific_acceptance': 'NOT_RUN', 'packages': []}
    canonical = {p.relative_to(CONTRACT).as_posix(): p.read_bytes() for p in files(CONTRACT)}
    for row in index['packages']:
        pkg = BASE / row['package_id']
        source_count = check_source_copies(pkg)
        copied = {p.relative_to(pkg / 'interface').as_posix(): p.read_bytes() for p in files(pkg / 'interface')}
        require(canonical == copied, f'{pkg.name}: shared interface copy drift')
        actual = {p.relative_to(pkg).as_posix(): p.read_bytes() for p in files(pkg)}
        manifest = v.strict_json(pkg / 'PACKAGE_MANIFEST.json')
        require(manifest['version'] == VERSION and manifest['revision'] == REVISION and row['revision'] == REVISION,
                f'{pkg.name}: identity mismatch')
        expected = {r['path']: r for r in manifest['files']}
        require(set(actual) == set(expected) | {'PACKAGE_MANIFEST.json'}, f'{pkg.name}: file manifest set mismatch')
        for path, entry in expected.items():
            require(len(actual[path]) == entry['bytes'] and digest(actual[path]) == entry['sha256'], f'{pkg.name}: file drift: {path}')
        arcpath = BASE / 'releases' / row['archive']
        data = arcpath.read_bytes()
        require(len(data) == row['bytes'] and digest(data) == row['sha256'], f'{pkg.name}: ZIP identity mismatch')
        require(arcpath.with_suffix('.zip.sha256').read_text(encoding='utf-8') == f"{row['sha256']}  {arcpath.name}\n", f'{pkg.name}: sidecar mismatch')
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            require(len(names) == len(set(names)) == row['file_count'] and archive.testzip() is None, f'{pkg.name}: ZIP corruption/duplicate')
            require(set(names) == {f'{pkg.name}/{p}' for p in actual}, f'{pkg.name}: ZIP file set mismatch')
            for path, content in actual.items():
                require(archive.read(f'{pkg.name}/{path}') == content, f'{pkg.name}: ZIP file differs: {path}')
        for p in pkg.rglob('*.json'):
            v.strict_json(p)
        links = 0
        for p in pkg.rglob('*.md'):
            if EXPERT_DIRNAME in p.parts:
                continue  # Preserve original scientific bracket notation byte-for-byte.
            for raw in re.findall(r'!?\[[^\]]*\]\((<[^>\n]+>|[^)\n]+)\)', p.read_text(encoding='utf-8')):
                target = raw.strip('<>')
                if urlsplit(target).scheme or target.startswith('#'):
                    continue
                resolved = (p.parent / unquote(target.split('#', 1)[0])).resolve()
                require(resolved.is_relative_to(pkg.resolve()) and resolved.exists(), f'{pkg.name}: external/missing local link: {target}')
                links += 1
        require(not v.validate_paths(pkg / 'examples/request.example.json'), f'{pkg.name}: top-level request invalid')
        scenarios = sorted((pkg / 'interface/examples').glob('*/request.json'))
        for request in scenarios:
            errors = v.validate_paths(request, request.parent / 'output/result.json', True)
            require(not errors, f'{pkg.name}: {request.parent.name}: {errors}')
        report['packages'].append({'package_id': pkg.name, 'version': VERSION, 'revision': REVISION,
                                  'archive_sha256': row['sha256'], 'file_count': len(actual),
                                  'source_copies_verified': source_count, 'closed_local_links': links,
                                  'interface_files_identical': len(canonical), 'synthetic_pairs_checked': len(scenarios)})
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--build', action='store_true', help='Replace current v0.1 packages and refresh manifests (explicit user scope)')
    group.add_argument('--check', action='store_true', help='Read-only verification (default)')
    args = parser.parse_args(argv)
    try:
        if args.build:
            build()
        report = check()
        if args.build:
            write_json(BASE / 'releases/PACKAGE_VERIFICATION.json', report)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        report = {'status': 'FAIL', 'error': str(exc)}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
