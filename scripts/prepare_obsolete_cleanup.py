"""Inventory explicitly superseded local copies; never deletes data or cluster resources."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/version-unification-20260927/cleanup-manifest.json'


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b''):
            result.update(block)
    return result.hexdigest()


def main():
    candidates = {}
    def add(path, reason, replacement):
        path = ROOT / path
        if not path.exists():
            return
        if not (ROOT / replacement).exists():
            raise ValueError('Replacement missing: ' + replacement)
        files = [path] if path.is_file() else sorted(p for p in path.rglob('*') if p.is_file())
        for file in files:
            if file.is_symlink() or not file.resolve().is_relative_to(ROOT):
                raise ValueError('Unsafe cleanup path')
            relative = file.relative_to(ROOT).as_posix()
            candidates[relative] = dict(path=relative, reason=reason, retained=replacement)

    for name in ('control-report-replay.json', 'control-report-replay.html'):
        old = 'reports/n12-validation-20260926/' + name
        new = 'reports/version-unification-20260927/' + name
        assert digest(ROOT / old) == digest(ROOT / new)
        add(old, 'byte-identical report duplicate', new)
    for old in ('reports/n05-duration-20260926/host-panel-docs.log',
                'reports/n05-duration-20260926/host-panel-docs-final.log',
                'reports/n12-validation-20260926/docs-check.log'):
        new = 'reports/version-unification-20260927/docs-check.log'
        assert digest(ROOT / old) == digest(ROOT / new)
        add(old, 'byte-identical documentation check duplicate', new)
    for old, new in (('desktop.png', 'antigen-report-desktop.png'),
                     ('mobile.png', 'antigen-report-mobile.png')):
        add('reports/user-report-20260926/' + old, 'superseded visual preview',
            'reports/user-report-20260926/' + new)

    # Keep each package's latest revision and all original preflight receipts.
    for parent in sorted((ROOT / 'deploy').iterdir()):
        if not parent.is_dir():
            continue
        revisions = sorted((p for p in parent.iterdir() if p.is_dir() and re.fullmatch(r'r\d+', p.name)),
                           key=lambda p: int(p.name[1:]))
        if len(revisions) < 2:
            continue
        latest = revisions[-1]
        for revision in revisions[:-1]:
            for name in ('configmap.yaml', 'configmap.json', 'deployment.patch.json', 'rollback.patch.json'):
                if (latest / name).exists():
                    add((revision / name).relative_to(ROOT), 'superseded deployment copy',
                        (latest / name).relative_to(ROOT).as_posix())

    # Build contexts are generated source copies, not native execution spools.
    groups = [('.tmp/science-fixes-20260916-r0', range(1,4), 'context', '.tmp/science-fixes-20260916-r04/context'),
              ('.tmp/resident-assembly-r0', range(1,5), 'context', '.tmp/resident-assembly-r05/context')]
    for prefix, versions, suffix, latest in groups:
        for version in versions:
            add(prefix + str(version) + '/' + suffix, 'superseded build source copy', latest)
    for old in ('.tmp/target-linux-build', '.tmp/target-linux-build-readable-20260912',
                '.tmp/target-linux-build-readable-20260912-r04'):
        add(old, 'superseded build source copy', '.tmp/target-linux-build-readable-20260912-r05')
    add('deploy/antigen-design-resident-20260915-r01/images/workers-linux-amd64.tar',
        'superseded pre-integration image export', 'deploy/antigen-resident-publish-20260916-r01/workers-linux-amd64.tar')
    add('.tmp/esmfold2-image-publish-20260916-r01/worker-linux-amd64.tar',
        'older image export copy', '.tmp/esmfold2-image-publish-20260916-r02/worker-linux-amd64.tar')
    for version in ('r01','r02'):
        folder = ROOT / ('.tmp/esmfold2-backend-publish-20260917-' + version)
        for path in folder.glob('*.tar'):
            latest = ROOT / '.tmp/esmfold2-backend-publish-20260917-r03' / path.name
            if latest.exists():
                add(path.relative_to(ROOT), 'superseded backend image export', latest.relative_to(ROOT).as_posix())

    # Preserve direct historical documentation and test fixture dependencies.
    references = []
    for folder in ('docs', 'tests'):
        for path in (ROOT / folder).rglob('*'):
            if path.is_file() and path.suffix in ('.md', '.py', '.json') and path.stat().st_size < 2 * 1024**2:
                references.append((path.relative_to(ROOT).as_posix(), path.read_text(encoding='utf8', errors='replace').replace('\\', '/')))
    protected = []
    for relative, row in list(candidates.items()):
        links = [name for name, text in references if relative in text]
        if links and row['reason'] != 'byte-identical report duplicate':
            protected.append(dict(path=relative, reason='referenced history or test input', references=links))
            del candidates[relative]
    rows = []
    for relative, row in sorted(candidates.items()):
        path = ROOT / relative
        rows.append(dict(row, bytes=path.stat().st_size, sha256=digest(path)))
    value = dict(status='PREPARED', scope='local superseded reports/build/deployment copies only',
        latest_source='deploy/version-unification/r01', files=rows, protected=protected,
        file_count=len(rows), bytes=sum(row['bytes'] for row in rows),
        preserved=['expert originals', 'frozen assets', 'native run evidence', 'credentials',
                   'current source and runtime assets', 'latest deployment and rollback',
                   'original preflight and image publication receipts'])
    OUT.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(dict(files=len(rows), GiB=round(value['bytes']/1024**3, 3), protected=len(protected))))


if __name__ == '__main__':
    main()
