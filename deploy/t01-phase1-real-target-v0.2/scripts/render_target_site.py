"""Render a new site bundle from explicit JSON; never apply it or embed credentials."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import yaml
from t01_phase1_real.deployment.site import render_site


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    rendered=render_site(json.loads(args.config.read_text(encoding='utf-8')))
    args.output.mkdir(parents=True,exist_ok=False)
    for name in ('application','administrator'):
        (args.output/(name+'.yaml')).write_text(yaml.safe_dump_all(rendered[name],sort_keys=False),encoding='utf-8')
    print(json.dumps({'status':'RENDERED_NOT_APPLIED','namespace':rendered['launcher']['namespace'],
        'production_status':'NOT_DEPLOYED','output':str(args.output.resolve())}))


if __name__=='__main__':main()
