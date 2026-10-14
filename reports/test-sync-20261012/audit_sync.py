import pathlib, subprocess, re, json

root = pathlib.Path.cwd()
out = root / 'reports/test-sync-20261012'
roots = ['src','tests','scripts','deploy','docs','reports','工作流设计','.gitignore','AGENTS.md','README.md','Dockerfile','Jenkinsfile','.dockerignore','pyproject.toml']
paths = set(filter(None, subprocess.check_output(['git','ls-files','--modified','--others','--exclude-standard','-z','--',*roots], stderr=subprocess.DEVNULL).decode().split('\0')))
selected, excluded, hits = [], [], []
patterns = {
    'private_key': rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',
    'token': rb'(?:AKIA[0-9A-Z]{16}|LTAI[0-9A-Za-z]{16,}|ghp_[A-Za-z0-9]{30,}|glpat-[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{15,})',
    'url_auth': rb'https?://[^\s/@:"<>]+:[^\s/@"<>]+@',
    'literal_credential': rb'(?i)["\x27](?:password|access[_-]?key|secret[_-]?key|token|signing[_-]?key|client[_-]?secret)["\x27]\s*:\s*["\x27]([^"\x27\r\n]{12,})["\x27]',
    'signed_url': rb'(?i)(?:X-Amz-Signature|signature|access_token|token)=[A-Za-z0-9%_+./-]{30,}',
}
for s in sorted(paths):
    p = root / s
    if not p.is_file() or s.startswith('reports/test-sync-20261012/'):
        continue
    if any(x.startswith(('test-work','deploy-test-work','codex_pytest')) for x in p.parts) or (s.startswith('reports/') and (p.suffix in ['.zip','.gz','.bin','.sqlite3','.before'] or 'runtime' in p.parts)):
        excluded.append(s)
        continue
    selected.append(s)
    raw = p.read_bytes()
    if p.suffix in ['.png','.docx','.xlsx','.pdf','.whl']:
        continue
    for kind, pattern in patterns.items():
        matches = list(re.finditer(pattern, raw))
        if matches:
            hits.append(dict(path=s,kind=kind,count=len(matches),lines=[raw.count(b'\n',0,m.start())+1 for m in matches[:8]]))
(out/'paths.json').write_text(json.dumps(selected,ensure_ascii=False),encoding='utf8')
(out/'excluded.json').write_text(json.dumps(excluded,ensure_ascii=False),encoding='utf8')
(out/'audit.json').write_text(json.dumps(hits,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(dict(files=len(selected),bytes=sum((root/s).stat().st_size for s in selected),excluded=len(excluded),hits=hits),ensure_ascii=True))
