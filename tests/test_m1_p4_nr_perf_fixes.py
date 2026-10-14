"""Deployment guards for the target nr verification and BLAST launch fixes."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import prepare_m1_p4_nr_blast_exec_fix as exec_fix
import prepare_m1_p4_nr_code_r02 as code_fix
import prepare_m1_p4_nr_policy_r03 as policy_fix


def test_target_code_patch_only_switches_immutable_code_configmap():
    live = {'metadata': {'resourceVersion': '2', 'uid': 'u', 'generation': 7},
            'spec': {'replicas': 1, 'strategy': {'type': 'Recreate'},
                     'template': {'spec': {'volumes': [
                         {'name': code_fix.OLD_NAME, 'configMap': {'name': code_fix.OLD_NAME}},
                         {'name': 'n03-nr-target'}]}}}}
    ops = code_fix.patch(live)
    assert ops[-1] == {'op': 'replace',
                       'path': '/spec/template/spec/volumes/0/configMap/name',
                       'value': code_fix.NAME}


def test_direct_blast_patch_keeps_eight_gib_pod_limit_and_mounts_wrapper():
    live = {'metadata': {'resourceVersion': '2', 'uid': 'u'},
            'spec': {'replicas': 1, 'strategy': {'type': 'Recreate'},
                     'template': {'spec': {
                         'containers': [{'name': 'service', 'volumeMounts': []},
                                        {'name': 'worker-blast',
                                         'resources': {'limits': {'memory': '8Gi'}},
                                         'volumeMounts': []}],
                         'volumes': []}}}}
    ops = exec_fix.patch(live)
    assert ops[2]['value'] == {'name': exec_fix.VOLUME, 'mountPath': exec_fix.MOUNT,
                               'subPath': 'blastp', 'readOnly': True}
    assert ops[3]['value'] == {'name': exec_fix.VOLUME,
                               'configMap': {'name': exec_fix.NAME, 'defaultMode': 493}}
    assert exec_fix.WRAPPER == '#!/bin/sh\nexec /blast/bin/blastp.REAL "$@"\n'


def test_persisted_receipt_policy_patch_switches_only_service_code_mount():
    live = {'metadata': {'resourceVersion': '2', 'uid': 'u'},
            'spec': {'replicas': 1, 'strategy': {'type': 'Recreate'},
                     'template': {'spec': {
                         'containers': [{'name': 'service', 'volumeMounts': [
                             {'name': 'p4-nr-fixes-r02', 'mountPath': policy_fix.MOUNT,
                              'subPath': 'p0', 'readOnly': True},
                             {'name': 'p4-nr-receipt', 'mountPath': '/etc/t01/blast-target-receipt.json',
                              'subPath': 'target-receipt.json', 'readOnly': True}]},
                                        {'name': 'worker-blast', 'resources': {'limits': {'memory': '16Gi'}}}],
                         'volumes': [{'name': 'p4-nr-receipt'}]}}}}
    operations = policy_fix.patch(live)
    assert operations[2]['value'] == {'name': policy_fix.VOLUME, 'mountPath': policy_fix.MOUNT,
                                      'subPath': 'policy.py', 'readOnly': True}
    assert operations[3]['value'] == {'name': policy_fix.VOLUME,
                                      'configMap': {'name': policy_fix.NAME}}
