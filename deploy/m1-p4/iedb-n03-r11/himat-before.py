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


HIMAT_PRINCIPAL = "himat-t01-test"
CARD_TYPE = "primer_design_output"
ATTACHMENT_PREFIX = "/antigen-design/attachments"
ATTACHMENT_TTL_SECONDS = 3600
TARGET_IEDB_MANIFEST_SHA256 = "96be17e60c108013d320558817037d081edbf8e3c0ed2f9facf83a2d818b6e12"
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
        request = {
            "protein_sequence": protein_sequence,
            "user_sequence_id": "himat_" + sha(protein_sequence.encode("ascii"))[:16],
            "host_species": host_species,
            "expression_host": None,
            "organism": None,
            "structure": None,
            "prediction": {"engine": "esmfold2", "seed": 1, "timeout_seconds": 7200},
            "analysis": {
                "topology": {"timeout_seconds": 600},
                "blast": {"database_id": "iedb-20260924-r01",
                          "database_manifest_sha256": TARGET_IEDB_MANIFEST_SHA256,
                          "thresholds": {"identity_percent_min": 70,
                                         "query_coverage_percent_min": 80},
                          "timeout_seconds": 7200},
                "bepipred": {"timeout_seconds": 900},
                # OI-003 does not permit inferring an MHC allele panel from a host name.
                "netmhc": None,
                "homology": None,
                "domains": None,
                "developability": {"dimension_weights": None, "target_ph": None,
                                   "target_ph_range": [4.0, 8.0], "timeout_seconds": 60},
            },
            "reuse_jobs": {},
            "timeout_seconds": 28800,
        }
        from ..development.workflow.engineering import MODE
        request['engineering_design'] = MODE
        key_parts = [protein_sequence, host_species, run_key, MODE, TARGET_IEDB_MANIFEST_SHA256]
        key_material = json.dumps(key_parts,
                                  ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        key = "himat-sequence-" + hashlib.sha256(key_material).hexdigest()[:48]
        value = self.service.submit(principal, {
            "idempotency_key": key,
            "request": request,
        })
        value["input_profile"] = "HIMAT_SEQUENCE_TARGET_IEDB_ENGINEERING_V1"
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
        nodes = status.get("nodes", {})
        completed = sum(row["state"] in {"succeeded", "failed", "skipped", "blocked", "unavailable"}
                        for row in nodes.values())
        current = [row["node_id"] for row in nodes.values() if row["state"] in {"queued", "running"}]
        return {"job_id": job_id, "run_id": status["run_id"], "state": status["state"],
                "terminal": False, "completed_nodes": completed, "total_nodes": len(nodes),
                "current_nodes": current, "scientific_gate": status["scientific_gate"],
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
            return markdown

    @staticmethod
    def node_issues(status):
        return [f"{row['node_id']} {name}: {row['state']} / {row.get('reason_code') or row.get('error_code') or 'UNKNOWN_REASON'}" + (f" / {row['detail']}" if row.get('detail') else '')
                for name, row in status.get('nodes', {}).items()
                if row['state'] in {'failed', 'timed_out', 'cancelled', 'blocked', 'unavailable', 'skipped'}]

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
        attachments = [
            {"attachmentId": "attachment_report", "fileName": "report.md", "fileType": "MD",
             "mimeType": "text/markdown", "fileUrl": self.attachment_url(principal, job_id, "report", sha(markdown_raw))},
            {"attachmentId": "attachment_zip", "fileName": report["filename"], "fileType": "ZIP",
             "mimeType": "application/zip", "fileUrl": self.attachment_url(principal, job_id, "zip", report["sha256"])},
        ]
        return {"type": CARD_TYPE, "data": {
            "status": "COMPLETED", "reportTitle": "抗原设计测试服工程报告",
            "summaryText": f"任务 {job_id} 已生成工程报告；后端结论 {result}。{execution_note}科学资格 CLOSED / false / NOT_DEPLOYED。",
            "primaryAttachmentId": "attachment_report", "attachments": attachments,
            "issues": issues,
        }}

    def _signature(self, path: str, owner: str, digest: str, expires: int) -> str:
        message = f"t01-himat-attachment-v1\n{path}\n{owner}\n{digest}\n{expires}".encode("utf-8")
        return hmac.new(self.signing_key, message, hashlib.sha256).hexdigest()

    def attachment_url(self, principal: Principal, job_id: str, kind: str, digest: str,
                       now: int | None = None) -> str:
        if JOB_PATTERN.fullmatch(job_id) is None or kind not in {"report", "zip"}:
            raise ServiceError("INVALID_REQUEST", "Invalid attachment identity", 422)
        path = f"{ATTACHMENT_PREFIX}/{job_id}/{kind}"
        expires = int(time.time() if now is None else now) + ATTACHMENT_TTL_SECONDS
        query = urlencode({"owner": principal.principal_id, "sha256": digest,
                           "expires": expires, "signature": self._signature(path, principal.principal_id, digest, expires)})
        return f"{self.base_url}{path}?{query}"

    def download(self, path: str, query: str, now: int | None = None) -> tuple[bytes, str, str, str]:
        match = re.fullmatch(re.escape(ATTACHMENT_PREFIX) + r"/(t01p1r-job-[0-9a-f]{32})/(report|zip)", path)
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
        if match.group(2) == "zip":
            raw, filename, media_type = report["content"], report["filename"], "application/zip"
        else:
            raw, filename, media_type = self.report_markdown(report), "report.md", "text/markdown; charset=utf-8"
        if sha(raw) != digest:
            raise ServiceError("INTEGRITY_ERROR", "Attachment bytes differ from signed report", 500)
        return raw, filename, media_type, digest
