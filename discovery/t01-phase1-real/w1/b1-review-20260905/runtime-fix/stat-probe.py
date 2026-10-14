from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import sqlite3
import time
root=Path(__file__).resolve().parents[1]/'.tmp/w1-sqlite-stat-probe'
root.mkdir(exist_ok=True)
path=root/'transient.sqlite3'
deadline=time.monotonic()+8
def churn():
    while time.monotonic()<deadline:
        with sqlite3.connect(path,timeout=5) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS fixture (id INTEGER)')
        db.close()
observed=[]
with ThreadPoolExecutor(2) as pool:
    future=pool.submit(churn)
    while time.monotonic()<deadline:
        for suffix in ['-wal','-shm']:
            target=Path(str(path)+suffix)
            try:
                value=target.lstat()
                if value.st_nlink==0:
                    observed.append(dict(file=target.name,st_nlink=value.st_nlink,st_mode=value.st_mode,
                                         attributes=value.st_file_attributes,exists_after_stat=target.exists()))
            except FileNotFoundError: pass
    future.result()
output=dict(zero_link_observations=len(observed),examples=observed[:8],scope='Owned SQLite sidecar churn; no hard links were created')
(root/'observations.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
print(json.dumps(output))
