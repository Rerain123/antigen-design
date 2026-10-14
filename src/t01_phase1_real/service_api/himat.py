"""Sequence-driven HiMat entry and private, expiring report capabilities."""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import re
import time
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from t01_phase1_real.common import sha

from .app import Principal, Service, ServiceError
from .object_storage import report_filenames


HIMAT_PRINCIPAL = "himat-t01-test"
CARD_TYPE = "primer_design_output"
ATTACHMENT_PREFIX = "/antigen-design/attachments"
ATTACHMENT_TTL_SECONDS = 3600
TARGET_IEDB_DATABASE_ID = "iedb-20261013-6l62-r01"
TARGET_IEDB_MANIFEST_SHA256 = "000695140d8fedf1cc897faba5356bf184928235a3417486448b3ec09c72992b"
TARGET_SWISSPROT_MANIFEST_SHA256 = "25d35d976d40808f50e0c1246c3a410b41360a6b42994493ef212fa0213a6bae"
JOB_PATTERN = re.compile(r"t01p1r-job-[0-9a-f]{32}\Z")
RUN_KEY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
SEQUENCE_PATTERN = re.compile(r"[ACDEFGHIKLMNPQRSTVWY]{9,999}\Z")
MAX_NESTED_DELIVERY_BYTES = 32 * 1024 * 1024
MAX_MARKDOWN_BYTES = 4 * 1024 * 1024


class HiMatIntegration:
    def __init__(self, service: Service, base_url: str, signing_key: bytes) -> None:
        parsed = urlsplit(base_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ServiceError("CONFIGURATION_INVALID", "HiMat attachment origin must be HTTPS", 500)
        if len(signing_key) < 32:
            raise ServiceError("CONFIGURATION_INVALID", "HiMat attachment signing key is too short", 500)
        self.service = service
        self.base_url = base_url.rstrip("/")
        self.signing_key = signing_key

    @classmethod
    def from_environment(cls, service: Service) -> "HiMatIntegration | None":
        if not any(row["principal"] == HIMAT_PRINCIPAL for row in service.credentials.inventory()):
            return None
        source = os.environ.get("T01_HIMAT_DOWNLOAD_KEY_FILE", "")
        base_url = os.environ.get("T01_HIMAT_ATTACHMENT_BASE_URL", "")
        if not source or not Path(source).is_absolute():
            raise ServiceError("CONFIGURATION_INVALID", "HiMat download signing key file required", 500)
        try:
            key = Path(source).read_bytes().strip()
        except OSError as exc:
            raise ServiceError("CONFIGURATION_INVALID", "HiMat download signing key unavailable", 500) from exc
        return cls(service, base_url, key)

    @staticmethod
    def is_himat(principal: Principal) -> bool:
        return principal.principal_id == HIMAT_PRINCIPAL

    def submit_sequence(self, principal: Principal, protein_sequence: str,
                        host_species: str, run_key: str = "first") -> dict[str, Any]:
        if not self.is_himat(principal) or "submit" not in principal.scopes:
            raise ServiceError("FORBIDDEN", "HiMat sequence submission is unavailable", 403)
        if not isinstance(protein_sequence, str) or SEQUENCE_PATTERN.fullmatch(protein_sequence) is None:
            raise ServiceError("INVALID_REQUEST", "Provide one exact uppercase AA20 protein sequence of 9..999 residues", 422)
        if not isinstance(host_species, str) or not 1 <= len(host_species) <= 128 or host_species != host_species.strip():
            raise ServiceError("HOST_SPECIES_REQUIRED", "Ask the user for the host species before submission", 422)
        if not isinstance(run_key, str) or RUN_KEY_PATTERN.fullmatch(run_key) is None:
            raise ServiceError("INVALID_REQUEST", "run_key must be a short safe label", 422)
        # Only the sequence, host and replay label come from HiMat. No structure,
        # design mask, database identity, threshold or scientific gate comes from the model.
        from ..development.netmhc.host_panel import options as host_options
        netmhc_options = host_options(host_species)
        request = {
            "protein_sequence": protein_sequence,
            "user_sequence_id": "himat_" + sha(protein_sequence.encode("ascii"))[:16],
            "host_species": host_species,
            "expression_host": None,
            "organism": None,
            "structure": None,
            "prediction": {"engine": "af3", "seed": 1, "timeout_seconds": 7200},
            "analysis": {
                "topology": {"timeout_seconds": 600},
                "blast": {"database_id": TARGET_IEDB_DATABASE_ID,
                          "database_manifest_sha256": TARGET_IEDB_MANIFEST_SHA256,
                          "thresholds": {"identity_percent_min": 70,
                                         "query_coverage_percent_min": 80},
                          "timeout_seconds": 7200},
                "bepipred": {"timeout_seconds": 900},
                # User-authorized provisional pig panel; other hosts retain A1 §7 fallback.
                "netmhc": netmhc_options,
                "homology": None,
                "domains": {"database_id":"swissprot-2026_03-r01",
                            "database_manifest_sha256":TARGET_SWISSPROT_MANIFEST_SHA256,
                            "organism_name":None,"entry_id":None,"parent":None,
                            "user_annotations":[],"timeout_seconds":60},
                "developability": {"dimension_weights": None, "target_ph": None,
                                   "target_ph_range": [4.0, 8.0], "timeout_seconds": 60},
            },
            "reuse_jobs": {},
            "timeout_seconds": 28800,
        }
        from ..development.workflow.engineering import MODE
        from ..development.workflow.revision_v2 import config as revision_config
        from ..development.workflow.revision_structure import SINGLE_MODEL_POLICY
        request['engineering_design'] = MODE
        # Persist the adopted version and its explicit budget for new HiMat runs.
        # Historical requests, results and confirmation decisions are immutable.
        # Isolate the WT and candidate routing adoption from previous report replay.
        request['revision_config'] = revision_config('himat-expert-v2-20261013-same-engine-v2',
                                                    model_policy=SINGLE_MODEL_POLICY)
        request['interaction_policy'] = 'PREAUTHORIZED_T4_CONTINUE_WITH_WARNING_V1'
        key_parts = [protein_sequence, host_species, run_key, MODE, "T4_HANDSHAKE_V1", TARGET_IEDB_MANIFEST_SHA256,
                     TARGET_SWISSPROT_MANIFEST_SHA256, netmhc_options['panel_manifest_sha256'], request['revision_config'], request['interaction_policy']]
        key_material = json.dumps(key_parts,
                                  ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        key = "himat-sequence-" + hashlib.sha256(key_material).hexdigest()[:48]
        value = self.service.submit(principal, {
            "idempotency_key": key,
            "request": request,
        })
        value["input_profile"] = "HIMAT_SEQUENCE_EXPERT_V2"
        value['rule_version'] = request['revision_config']['rule_version']
        value['calculation_config_id'] = request['revision_config']['calculation_config_id']
        value['parameter_status'] = request['revision_config']['parameter_status']
        value['interaction_policy'] = request['interaction_policy']
        value["sequence_length"] = len(protein_sequence)
        value["sequence_sha256"] = sha(protein_sequence.encode("ascii"))
        value["host_species"] = host_species
        value['design_input_status'] = 'PENDING_BACKEND_EVIDENCE'
        return value

    def check(self, principal: Principal, job_id: str) -> dict[str, Any]:
        if not self.is_himat(principal) or "query" not in principal.scopes:
            raise ServiceError("FORBIDDEN", "HiMat progress query is unavailable", 403)
        status = self.service.status(principal, job_id)
        if status["terminal"]:
            return self.card(principal, job_id, status=status)
        from .progress import project
        progress = project(status.get("nodes", {}))
        return {"job_id": job_id, "run_id": status["run_id"], "state": status["state"],
                "pending_confirmation":status.get('pending_confirmation'),
                "design_execution":status.get('design_execution'),
                "controller":status.get('controller'),
                "terminal": False, **progress, "scientific_gate": status["scientific_gate"],
                "usable_for_pipeline": status["usable_for_pipeline"],
                "production_status": status["production_status"]}

    @staticmethod
    def report_markdown(report: dict[str, Any]) -> bytes:
        """Prefer N18's actual report when its verified package is present."""
        with zipfile.ZipFile(io.BytesIO(report["content"])) as workflow:
            if "local-delivery.zip" not in workflow.namelist():
                return report["report_markdown"].encode("utf-8")
            nested = workflow.getinfo("local-delivery.zip")
            if nested.file_size > MAX_NESTED_DELIVERY_BYTES:
                raise ServiceError("REPORT_TOO_LARGE", "N18 delivery exceeds the attachment limit", 413)
            with zipfile.ZipFile(io.BytesIO(workflow.read(nested))) as delivery:
                item = delivery.getinfo("report.md")
                if item.file_size > MAX_MARKDOWN_BYTES:
                    raise ServiceError("REPORT_TOO_LARGE", "N18 report exceeds the preview limit", 413)
                markdown = delivery.read(item)
            # The nested N18 package can omit prediction failures because its WT
            # producer only references successful structure ingestion. The outer
            # verified workflow report contains every actual child and skip.
            if 'workflow-report.md' in workflow.namelist():
                detail = workflow.getinfo('workflow-report.md')
                if detail.file_size > MAX_MARKDOWN_BYTES:
                    raise ServiceError('REPORT_TOO_LARGE', 'Workflow detail exceeds the preview limit', 413)
                markdown += b'\n\n' + '## 工作流实际执行状态\n\n'.encode('utf-8') + workflow.read(detail)
            if 'workflow.json' in workflow.namelist():
                detail=workflow.getinfo('workflow.json')
                if detail.file_size>MAX_NESTED_DELIVERY_BYTES:
                    raise ServiceError('REPORT_TOO_LARGE','Workflow facts exceed preview limit',413)
                from ..development.workflow.reporting import design_fact,text
                facts=design_fact(json.loads(workflow.read(detail)).get('nodes',{}))
                # Present verified execution facts first; preserve the archived package bytes.
                outcome=('结果：DESIGN_NOT_EXECUTED\n\n' if facts['status']=='NOT_EXECUTED' else '')
                markdown=('# 本次实际执行结论\n\n'+outcome+text(facts)+'\n\n'+
                    '以下为原始工程报告及工作流明细。\n\n').encode('utf-8')+markdown
            return markdown

    @staticmethod
    def node_issues(status):
        return [f"{row['node_id']} {name}: {row['state']} / {row.get('reason_code') or row.get('error_code') or 'UNKNOWN_REASON'}" + (f" / {row['detail']}" if row.get('detail') else '')
                for name, row in status.get('nodes', {}).items()
                if row['state'] in {'failed', 'timed_out', 'cancelled', 'blocked', 'unavailable', 'skipped'}]

    @staticmethod
    def report_html(report):
        from .user_report import from_workflow_package
        try:
            raw = from_workflow_package(report['content'],native_results=report.get('native_results'))
        except (ValueError, KeyError, zipfile.BadZipFile) as exc:
            raise ServiceError('REPORT_INVALID', 'Structured report could not be rendered', 500) from exc
        if raw is not None and len(raw) > MAX_MARKDOWN_BYTES:
            raise ServiceError('REPORT_TOO_LARGE', 'User report exceeds the attachment limit', 413)
        return raw

    def card(self, principal: Principal, job_id: str,
             status: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.is_himat(principal) or "download" not in principal.scopes:
            raise ServiceError("FORBIDDEN", "HiMat report card is unavailable", 403)
        status = status or self.service.status(principal, job_id)
        if not status["terminal"]:
            raise ServiceError("REPORT_NOT_AVAILABLE", "Workflow has not reached a terminal state", 409)
        if status["state"] != "succeeded":
            return {"type": CARD_TYPE, "data": {
                "status": "FAILED", "reportTitle": "抗原设计测试任务未完成",
                "summaryText": f"任务 {job_id} 终态为 {status['state']}；科学资格 CLOSED / false / NOT_DEPLOYED。",
                "primaryAttachmentId": None, "attachments": [],
                "issues": list(dict.fromkeys([status["error_code"] or status["state"]] + self.node_issues(status))),
            }}
        report = self.service.report(principal, job_id)
        names = report_filenames(report['report_name'])
        markdown_raw = self.report_markdown(report)
        markdown = markdown_raw.decode("utf-8")
        result = next((line.partition("：")[2].strip() for line in markdown.splitlines()
                       if line.startswith("结果：")), None)
        issues: list[str] = []
        in_sources = False
        for line in markdown.splitlines():
            if line == "## 来源与缺项":
                in_sources = True
                continue
            if in_sources and line.startswith("## "):
                break
            if in_sources and line.startswith("- "):
                issues.append(line[2:])
        nodes = status.get("nodes", {})
        if result is None:
            design = nodes.get("design", {})
            delivery = nodes.get("local_delivery", {})
            result = f"N11={design.get('state', 'unknown')}; N18={delivery.get('state', 'unknown')}"
        issues = list(dict.fromkeys(self.node_issues(status) + issues))
        failures = sum(row['state'] in {'failed', 'timed_out', 'cancelled'} for row in nodes.values())
        execution_note = f'计算含 {failures} 项失败，报告交付不表示计算成功。' if failures else '节点跳过及部分计算见缺项说明。'
        from ..development.workflow.reporting import design_fact,text
        fact=design_fact(nodes)
        if fact['status'] not in ('EXECUTED','UNKNOWN'):result='DESIGN_'+fact['status'] if fact['status']!='NOT_EXECUTED' else 'DESIGN_NOT_EXECUTED'
        execution_note=text(fact)+execution_note
        if report.get('native_results') is not None:
            with zipfile.ZipFile(io.BytesIO(report['content'])) as archive:
                revision=json.loads(archive.read('workflow.json'))['expert_revision']
            if revision:
                from .native_report import unique_candidates
                generated=revision['formal_records'];unique=unique_candidates(generated)
                result='PARTIAL_NATIVE_RESULTS' if revision.get('coverage_complete') is False else 'NATIVE_RESULTS'
                execution_note=(f'正式生成 {len(generated)} 条，去重后 {len(unique)} 条；完整验收 '
                                f"{revision['acceptance_status']}。"+execution_note)
            execution_note='已计算的 WT 数值、逐项缺项原因和完整原始文件见附件。'+execution_note
        attachments = [
            {"attachmentId": "attachment_report", "fileName": names['report'], "fileType": "MD",
             "mimeType": "text/markdown", "fileUrl": self.attachment_url(principal, job_id, "report", sha(markdown_raw))},
            {"attachmentId": "attachment_zip", "fileName": report["filename"], "fileType": "ZIP",
             "mimeType": "application/zip", "fileUrl": self.attachment_url(principal, job_id, "zip", report["sha256"])},
        ]
        user_html = self.report_html(report)
        if user_html is not None:
            attachments.append({"attachmentId": "attachment_user_report", "fileName": names['html'],
                "fileType": "HTML", "mimeType": "text/html",
                "fileUrl": self.attachment_url(principal, job_id, "html", sha(user_html))})
        native = None
        if report.get('native_results') is not None:
            native = self.service.native_report(principal, job_id, verified_report=report)
            attachments.append({"attachmentId":"attachment_native_results", "fileName":native['filename'],
                "fileType":"ZIP", "mimeType":"application/zip",
                "fileUrl":self.attachment_url(principal,job_id,"native",native['sha256'])})
        published = self.service.publish_report_files(principal, job_id, report, markdown_raw,
            html=user_html, native=native) if getattr(self.service, 'report_publisher', None) is not None else []
        return {"type": CARD_TYPE, "data": {
            "status": "COMPLETED", "reportTitle": "抗原设计分析报告" if user_html is not None else "抗原设计测试服工程报告",
            "summaryText": f"任务 {job_id} 已生成工程报告；报告名称 {report['report_name']}（北京时间）；后端结论 {result}。{execution_note}科学资格 CLOSED / false / NOT_DEPLOYED。",
            "reportName": report['report_name'], "publicationStatus": "verified" if published else "disabled",
            "storageAttachments": published,
            "primaryAttachmentId": "attachment_user_report" if user_html is not None else "attachment_report", "attachments": attachments,
            "issues": issues,
        }}

    def _signature(self, path: str, owner: str, digest: str, expires: int) -> str:
        message = f"t01-himat-attachment-v1\n{path}\n{owner}\n{digest}\n{expires}".encode("utf-8")
        return hmac.new(self.signing_key, message, hashlib.sha256).hexdigest()

    def attachment_url(self, principal: Principal, job_id: str, kind: str, digest: str,
                       now: int | None = None) -> str:
        if JOB_PATTERN.fullmatch(job_id) is None or kind not in {"report", "zip", "html", "native"}:
            raise ServiceError("INVALID_REQUEST", "Invalid attachment identity", 422)
        path = f"{ATTACHMENT_PREFIX}/{job_id}/{kind}"
        expires = int(time.time() if now is None else now) + ATTACHMENT_TTL_SECONDS
        query = urlencode({"owner": principal.principal_id, "sha256": digest,
                           "expires": expires, "signature": self._signature(path, principal.principal_id, digest, expires)})
        return f"{self.base_url}{path}?{query}"

    def download(self, path: str, query: str, now: int | None = None) -> tuple[bytes, str, str, str]:
        match = re.fullmatch(re.escape(ATTACHMENT_PREFIX) + r"/(t01p1r-job-[0-9a-f]{32})/(report|zip|html|native)", path)
        if match is None:
            raise ServiceError("NOT_FOUND", "Attachment not found", 404)
        try:
            params = parse_qs(query, keep_blank_values=True, strict_parsing=True)
            if set(params) != {"owner", "sha256", "expires", "signature"} or any(len(v) != 1 for v in params.values()):
                raise ValueError("Invalid capability parameters")
            owner, digest, signature = (params[key][0] for key in ("owner", "sha256", "signature"))
            expires = int(params["expires"][0])
        except (ValueError, KeyError):
            raise ServiceError("FORBIDDEN", "Invalid attachment capability", 403) from None
        if expires < int(time.time() if now is None else now) or expires > int(time.time() if now is None else now) + ATTACHMENT_TTL_SECONDS or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ServiceError("FORBIDDEN", "Attachment capability expired or invalid", 403)
        if not hmac.compare_digest(signature, self._signature(path, owner, digest, expires)):
            raise ServiceError("FORBIDDEN", "Attachment capability signature differs", 403)
        row = next((item for item in self.service.credentials.inventory() if item["principal"] == owner), None)
        if row is None or owner != HIMAT_PRINCIPAL or "download" not in row["scopes"]:
            raise ServiceError("FORBIDDEN", "Attachment owner is unavailable", 403)
        principal = Principal(owner, frozenset(row["scopes"]), row["token_sha256"])
        report = self.service.report(principal, match.group(1))
        names = report_filenames(report['report_name'])
        if match.group(2) == "native":
            native = self.service.native_report(principal, match.group(1), verified_report=report)
            raw, filename, media_type = native['content'], native['filename'], native['media_type']
        elif match.group(2) == "zip":
            raw, filename, media_type = report["content"], report["filename"], "application/zip"
        elif match.group(2) == "html":
            raw = self.report_html(report)
            if raw is None:
                raise ServiceError('REPORT_NOT_AVAILABLE', 'Structured user report unavailable', 404)
            filename, media_type = names['html'], "text/html; charset=utf-8"
        else:
            raw, filename, media_type = self.report_markdown(report), names['report'], "text/markdown; charset=utf-8"
        if sha(raw) != digest:
            raise ServiceError("INTEGRITY_ERROR", "Attachment bytes differ from signed report", 500)
        return raw, filename, media_type, digest
