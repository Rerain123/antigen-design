"""Render an offline user report from an existing engineering data.json.

Does not run tools, modify source evidence, or contact the server.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from t01_phase1_real.service_api.user_report import render


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--workflow',type=Path)
    parser.add_argument('--preview-note',default='')
    parser.add_argument('--replace-preview',action='store_true',help='Replace only an existing generated HTML preview, never a source file')
    args=parser.parse_args()
    data=json.loads(args.data.read_bytes())
    workflow=json.loads(args.workflow.read_bytes()) if args.workflow else None
    if workflow and 'records' in workflow:
        parent=next(r for r in workflow['records'] if r['job']['tool_id']=='t01.real.local_workflow')
        workflow={**parent['job'],'nodes':parent['execution']['nodes']}
    raw=render(data,workflow,preview_note=args.preview_note)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.output.resolve()==args.data.resolve() or (args.workflow and args.output.resolve()==args.workflow.resolve()):
        parser.error('Output must differ from source evidence')
    if args.output.suffix.lower()!='.html':parser.error('Output must be an HTML file')
    if args.replace_preview and args.output.exists() and not args.output.read_bytes().startswith(b'<!doctype html>'):
        parser.error('Only a generated HTML preview can be replaced')
    with args.output.open('wb' if args.replace_preview else 'xb') as stream:stream.write(raw)
    print(str(args.output.resolve()))


if __name__=='__main__':main()
