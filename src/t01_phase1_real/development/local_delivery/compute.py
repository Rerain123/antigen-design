import io
import zipfile
from ...common import decode,encode,sha
from . import policy

def evaluate(body,files):
    receipts=decode(files['input/source-receipts.json'])
    values={n:decode(files['input/'+n+'-result.json']) for n in policy.PRODUCERS if receipts[n]['state']=='available'}
    report=(values.get('variant_report') or {}).get('report');wt=(values.get('wt_draft') or {}).get('draft')
    reference=(values.get('wt_reference') or {}).get('reference');records=(report or {}).get('records',[])
    gate=(wt or {}).get('gate') or {};gate_status=gate.get('status')
    outcome='ALL_EXCLUDED' if report and report['outcome']=='ALL_EXCLUDED' else 'ENGINEERING_RECORDS_REVIEW_REQUIRED' if records else \
        'UPSTREAM_FAILED' if receipts['variant_report']['state']=='failed' else \
        'WT_ROUTE_REVIEW_REQUIRED' if gate_status=='NOT_SUITABLE_FOR_DESIGN' else \
        'DESIGN_ELIGIBLE_RELEASE_CLOSED' if gate_status=='SUITABLE_FOR_DESIGN' else \
        'DESIGN_INPUTS_UNAVAILABLE' if gate_status=='INPUT_INSUFFICIENT_OR_NOT_EVALUATED' else \
        'DESIGN_NOT_EXECUTED' if receipts['variant_report']['state']=='missing' else 'DESIGN_INPUTS_UNAVAILABLE'
    gaps=[dict(source=n,code=r['state'].upper() if r['state']!='available' else 'DEVELOPMENT_UNREVIEWED') for n,r in receipts.items() if n in policy.PRODUCERS]
    # Direct assembly succeeded does not imply that its upstream calculations did.
    def disclose(tree,prefix):
        for name,receipt in tree.items():
            if not isinstance(receipt,dict):continue
            path=prefix+'/'+name
            state=receipt.get('state')
            if state in ('failed','missing','pending'):
                gaps.append(dict(source=path,code=receipt.get('error_code') or 'UPSTREAM_'+state.upper()))
            disclose(receipt.get('upstream',{}),path)
    for name in policy.PRODUCERS:
        disclose(receipts.get(name,{}).get('upstream',{}),name)
    assessments=(wt or {}).get('assessments',{})
    n10=((assessments.get('developability') or {}).get('observations') or {}).get('developability') or {}
    if n10 and n10.get('n10_complete') is not True:
        gaps.append(dict(source='N10',code='PARTIAL_DEVELOPABILITY'))
        gaps.extend(dict(source='N10/'+name,code=reason) for name,reason in n10.get('excluded_dimensions',{}).items())
    if reference and not any(r.get('state')=='available' for r in reference.get('engines',{}).values()):
        failed=any(r.get('state')=='failed' for r in reference.get('engines',{}).values())
        gaps.append(dict(source='N17',code='NO_USABLE_NATIVE_SCAN_RESULT' if failed else 'NO_NATIVE_SCAN_EXECUTED'))
    gaps.extend(dict(source='N16:'+r['subject'],code=r['reason']) for r in receipts['dna'] if r['reason'])
    if not receipts['dna']:gaps.append(dict(source='N16',code='DNA_NOT_PROVIDED'))
    gaps.extend(dict(source='delivery',code=c) for c in ('OI_013_AGENT_C_INTERFACE_UNSIGNED','OI_014_CANDIDATE_RECORD_MAPPING_UNSIGNED','SCIENTIFIC_GATES_NOT_RELEASED'))
    for note in (report or {}).get('engineering_adjustments',[]):
        gaps.append(dict(source='N14',code=note['code'],message=note['message']))
    data=dict(kind='LOCAL_ENGINEERING_DELIVERY_PACKAGE',subject=dict(kind='WT',protein_sequence=body['protein_sequence'],
        sequence_sha256=sha(body['protein_sequence'].encode()),host_species=body['host_species'],expression_host=body['expression_host']),
        outcome=outcome,business_route=gate.get('route'),design_applicability_gate=gate or None,
        wt_draft=wt,variant_report=report,wt_reference=reference,dna=receipts['dna'],
        best_candidate=None,formal_candidate_id=None,candidate_record_complete=False,formal_wt_delivery=False,
        agent_c_payload=None,automatic_handoff=False,scientific_pass=None,production_status='NOT_DEPLOYED',
        source_receipts=receipts,missing_conditions=gaps,
        methods={n:values[n].get('method_summary') for n in values},
        export_policy=dict(scope='REGISTERED_RESULT_AND_REQUEST_ARTIFACTS_ONLY',
            raw_tool_files='REFERENCE_ONLY_IN_ORIGINAL_RUNTIME',server_models_and_licensed_tools='NOT_COPIED',credentials='NOT_INCLUDED'),
        review_reasons=[dict(code='LOCAL_ASSEMBLY_IS_NOT_PHASE1_COMPLETION')])
    if 'input/workflow-n17.json' in files:
        data['n17_execution']=decode(files['input/workflow-n17.json'])
        gaps.extend(dict(source='N17/'+n,code=r['reason_code']) for n,r in data['n17_execution']['engines'].items() if r.get('reason_code'))
    if 'input/workflow-design.json' in files:
        workflow=decode(files['input/workflow-design.json']);fact=workflow['design']
        data['design_execution']=fact
        if 'n12_validation' in workflow:data['n12_validation']=workflow['n12_validation']
        if fact['status']!='EXECUTED':
            data['outcome']='DESIGN_'+fact['status'] if fact['status']!='NOT_EXECUTED' else 'DESIGN_NOT_EXECUTED'
            gaps.append(dict(source='N11',code=fact.get('reason_code') or fact['status']))
    from .m1 import extend
    extend(data,files)
    return data

def readable(d):
    lines=['# 本地工程交付报告','',f"结果：{d['outcome']}",'',
        '开发未签收。不是正式 CandidateRecord 或 AgentCHandoff；不自动交接 Agent C。',
        f"WT SHA-256：{d['subject']['sequence_sha256']}",'',
        '## 变体结论','', '| 变体 | 结果 | 淘汰原因 |','|---|---|---|']
    for r in (d['variant_report'] or {}).get('records',[]):
        lines.append('| '+r['id']+' | '+r['disposition']+' | '+', '.join(e['code'] for e in r['exclusion_reasons'])+' |')
    if 'design_execution' in d:
        from ..workflow.reporting import text
        lines[4:4]=[text(d['design_execution']),'']
    lines+=['', '最佳候选：无。'+('候选设计未执行。' if d.get('design_execution',{}).get('status')=='NOT_EXECUTED' else '')+
        '正式排名与资格未开放。','','## 来源与缺项','']
    lines.extend('- '+g['source']+': '+g['code'] for g in d['missing_conditions'])
    for note in (d.get('variant_report') or {}).get('engineering_adjustments',[]):
        lines.extend(['', '### 待专家确认的临时工程调整', '', note['code'], '', note['message']])
    if d.get('dna'):
        lines+=['','## 逐候选 DNA（工程结果，待复核）','']
        for row in d['dna']:
            dna=row.get('dna') or {};seq=dna.get('optimized_dna') or dna.get('initial_dna')
            lines += [row['subject']+': '+str(row.get('source_status'))+' / '+str(row.get('reason')),
                '```text',seq or '无可用 DNA','```','']
    from .m1 import readable as m1_readable
    lines.extend(m1_readable(d))
    lines+=['','方法、扫描范围、原始 ArtifactRef 和逐层缺项见 [机器报告](data.json)。',
        '实际包内文件及 hash 见 [清单](manifest.json)。原始工具产物留在原运行根，包内保留登记引用。','']
    return '\n'.join(lines).encode('utf-8')

def package(body,files,data):
    contents={'data.json':encode(data),'report.md':readable(data),'request.json':encode(body)}
    for index,row in enumerate(data.get('dna') or [],1):
        d=row.get('dna') or {};seq=d.get('optimized_dna') or d.get('initial_dna')
        if seq:
            kind='optimized-engineering' if d.get('optimized_dna') else 'unoptimized-fallback'
            contents[f'dna/candidate-{index}-{kind}.fasta']=('>candidate-'+str(index)+' '+kind+'\n'+seq+'\n').encode()
            contents[f'dna/candidate-{index}-source.json']=encode(row)
    if 'n16' in data:
        contents['n16-condition.json']=encode(data['n16'])
        contents['n17-execution.json']=encode(data['n17_execution'])
        contents['agent-c-preview.json']=encode(data['agent_c_preview'])
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
    return {'output/package.zip':output.getvalue(),'output/report.md':contents['report.md'],
        'output/data.json':contents['data.json'],'output/manifest.json':contents['manifest.json'],
        'output/package-manifest.json':contents['manifest.json']}
