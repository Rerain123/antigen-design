"""Restore HiMat test submit scope only after deployed sequence checks pass."""

from __future__ import annotations

import base64
import json
import subprocess

import prepare_m1_p1_deploy as common
import prepare_himat_sequence_deploy as deployment


SECRET = "antigen-design-credentials"
PRINCIPAL = "himat-t01-test"
VERIFICATION = common.ROOT / "discovery/t01-phase1-real/m1-p4-20260922/himat-sequence-deployment-r04.json"
TESTS = common.ROOT / "discovery/t01-phase1-real/m1-p4-20260922/himat-sequence-full-r04.junit.xml"


def main() -> None:
    evidence = json.loads(VERIFICATION.read_bytes())
    if evidence["status"] != "HIMAT_SEQUENCE_DEPLOYED_HASH_PASS" or \
       evidence["source_hashes"] != deployment.hashes():
        raise RuntimeError("Deployed source evidence is stale")
    import xml.etree.ElementTree as ET
    root = ET.parse(TESTS).getroot()
    suite = root.find("testsuite") if root.tag != "testsuite" else root
    if suite is None or int(suite.attrib["failures"]) or int(suite.attrib["errors"]):
        raise RuntimeError("Complete regression has not passed")
    state = common.idle()
    if state["active_jobs"] or state["gpu_state"]["phase"] != "idle":
        raise RuntimeError("Refusing singleton restart while work is active")
    secret = json.loads(subprocess.check_output(common.K + ["get", "secret", SECRET, "-o", "json"]))
    document = json.loads(base64.b64decode(secret["data"]["credentials.json"]))
    rows = [row for row in document["credentials"] if row["principal"] == PRINCIPAL]
    if len(rows) != 1 or set(rows[0]["scopes"]) != {"query", "download"}:
        raise RuntimeError("Unexpected HiMat principal or scope set")
    rows[0]["scopes"] = ["submit", "query", "download"]
    secret["data"]["credentials.json"] = base64.b64encode(
        json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    secret["metadata"].pop("managedFields", None)
    subprocess.run(common.K + ["replace", "-f", "-"],
                   input=json.dumps(secret, separators=(",", ":")).encode("utf-8"),
                   stdout=subprocess.DEVNULL, check=True)
    subprocess.run(common.K + ["rollout", "restart", "deployment/antigen-design"],
                   stdout=subprocess.DEVNULL, check=True)
    subprocess.run(common.K + ["rollout", "status", "deployment/antigen-design", "--timeout=300s"],
                   stdout=subprocess.DEVNULL, check=True)
    observed = common.remote("""import json,urllib.request
from pathlib import Path
doc=json.loads(Path('/run/secrets/t01/credentials.json').read_bytes())
row=next(item for item in doc['credentials'] if item['principal']=='himat-t01-test')
body=json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{
    'name':'t01_phase1_real_service_v01.tool.workflow.submit_sequence',
    'arguments':{'protein_sequence':'ACDEFGHI','host_species':'Homo sapiens'}}}).encode()
req=urllib.request.Request('http://127.0.0.1:18083/mcp',data=body,headers={
    'Content-Type':'application/json','Authorization':'Bearer '+row['token']})
with urllib.request.urlopen(req,timeout=15) as response: result=json.load(response)
print(json.dumps({'scopes':row['scopes'],
    'invalid_sequence_rejected':result['result']['structuredContent']['error']['code']=='INVALID_REQUEST'}))
""")
    if set(observed["scopes"]) != {"submit", "query", "download"} or not observed["invalid_sequence_rejected"]:
        raise RuntimeError("Sequence submission activation failed")
    print("HIMAT_SEQUENCE_SUBMISSION_ACTIVE_NO_JOB_CREATED")


if __name__ == "__main__":
    main()
