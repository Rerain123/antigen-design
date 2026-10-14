import io
import zipfile
from ...common import decode,encode,sha
from . import policy

def evaluate(body,files):
    receipts=decode(files['input/source-receipts.json'])
    values={n:decode(files['input/'+n+'-result.json']) for n in policy.PRODUCERS if receipts[n]['state']=='available'}
    report=(values.get('variant_report') or {}).get('report');wt=(values.get('wt_draft') or {}).get('draft')
    reference=(values.get('wt_reference') or {}).get('reference');records=(report or {}).get('records',[])
    outcome='ALL_EXCLUDED' if report and report['outcome']=='ALL_EXCLUDED' else 'ENGINEERING_RECORDS_REVIEW_REQUIRED' if records else \
        'UPSTREAM_FAILED' if receipts['variant_report']['state']=='failed' else 'DESIGN_NOT_EXECUTED' if receipts['variant_report']['state']=='missing' else 'DESIGN_INPUTS_UNAVAILABLE'
    gaps=[dict(source=n,code=r['state'].upper() if r['state']!='available' else 'DEVELOPMENT_UNREVIEWED') for n,r in receipts.items() if n in policy.PRODUCERS]
    gaps.extend(dict(source='N16:'+r['subject'],code=r['reason']) for r in receipts['dna'])
    if not receipts['dna']:gaps.append(dict(source='N16',code='DNA_NOT_PROVIDED'))
    gaps.extend(dict(source='delivery',code=c) for c in ('OI_013_AGENT_C_INTERFACE_UNSIGNED','OI_014_CANDIDATE_RECORD_MAPPING_UNSIGNED','SCIENTIFIC_GATES_NOT_RELEASED'))
    return dict(kind='LOCAL_ENGINEERING_DELIVERY_PACKAGE',subject=dict(kind='WT',protein_sequence=body['protein_sequence'],
        sequence_sha256=sha(body['protein_sequence'].encode()),host_species=body['host_species'],expression_host=body['expression_host']),
        outcome=outcome,wt_draft=wt,variant_report=report,wt_reference=reference,dna=receipts['dna'],
        best_candidate=None,formal_candidate_id=None,candidate_record_complete=False,formal_wt_delivery=False,
        agent_c_payload=None,automatic_handoff=False,scientific_pass=None,production_status='NOT_DEPLOYED',
        source_receipts=receipts,missing_conditions=gaps,
        methods={n:values[n].get('method_summary') for n in values},
        export_policy=dict(scope='REGISTERED_RESULT_AND_REQUEST_ARTIFACTS_ONLY',
            raw_tool_files='REFERENCE_ONLY_IN_ORIGINAL_RUNTIME',server_models_and_licensed_tools='NOT_COPIED',credentials='NOT_INCLUDED'),
        review_reasons=[dict(code='LOCAL_ASSEMBLY_IS_NOT_PHASE1_COMPLETION')])

def readable(d):
    lines=['# 本地工程交付报告','',f"结果：{d['outcome']}",'',
        '开发未签收。不是正式 CandidateRecord 或 AgentCHandoff；不自动交接 Agent C。',
        f"WT SHA-256：{d['subject']['sequence_sha256']}",'',
        '## 变体结论','', '| 变体 | 结果 | 淘汰原因 |','|---|---|---|']
    for r in (d['variant_report'] or {}).get('records',[]):
        lines.append('| '+r['id']+' | '+r['disposition']+' | '+', '.join(e['code'] for e in r['exclusion_reasons'])+' |')
    lines+=['','最佳候选：无。正式排名与资格未开放。','','## 来源与缺项','']
    lines.extend('- '+g['source']+': '+g['code'] for g in d['missing_conditions'])
    lines+=['','方法、扫描范围、原始 ArtifactRef 和逐层缺项见 [机器报告](data.json)。',
        '实际包内文件及 hash 见 [清单](manifest.json)。原始工具产物留在原运行根，包内保留登记引用。','']
    return '\n'.join(lines).encode('utf-8')

def package(body,files,data):
    contents={'data.json':encode(data),'report.md':readable(data),'request.json':encode(body)}
    for n in policy.PRODUCERS:
        for suffix in ('request','result'):
            key='input/'+n+'-'+suffix+'.json'
            if key in files:contents['sources/'+n+'-'+suffix+'.json']=files[key]
    contents['manifest.json']=encode(dict(kind='LOCAL_ENGINEERING_FILE_MANIFEST',
        self_inclusion=False,files=[dict(path=n,size_bytes=len(v),sha256=sha(v)) for n,v in sorted(contents.items())]))
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED) as z:
        for name,raw in sorted(contents.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_STORED;z.writestr(info,raw)
    return {'output/package.zip':output.getvalue(),'output/report.md':contents['report.md'],'output/package-manifest.json':contents['manifest.json']}
