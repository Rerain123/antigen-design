"""Discovery-only checks: loading guidance must never start scientific work."""
import pytest

from t01_phase1_real.service_api.app import Principal
from t01_phase1_real.service_api.himat import HiMatIntegration
from t01_phase1_real.service_api.transport import MCPApplication


class NoExecutionService:
    def __getattr__(self, name):
        pytest.fail(f"MCP metadata discovery accessed execution service: {name}")


def application():
    service = NoExecutionService()
    adapter = HiMatIntegration(service, "https://example.test", b"k" * 32)
    return MCPApplication(service, adapter)


def owner(name="himat-t01-test"):
    return Principal(name, frozenset({"query"}), "test-not-a-credential")


def discover(app, principal, method, params=None):
    status, response = app.dispatch(principal, {
        "jsonrpc": "2.0", "id": 1, "method": method, "params": params or {},
    })
    assert status == 200 and "error" not in response
    return response["result"]


@pytest.mark.parametrize("version", ["2024-11-05", "2025-03-26", "2025-06-18"])
def test_initialize_delivers_workflow_guide_without_executing_or_loading_prompt(version):
    value = discover(application(), owner(), "initialize", {
        "protocolVersion": version, "capabilities": {},
        "clientInfo": {"name": "guide-test", "version": "1"},
    })
    assert value["protocolVersion"] == version
    assert value["capabilities"] == {"tools": {"listChanged": False}}
    text = value["instructions"]
    for required in ("workflow_submit_sequence", "workflow_check", "workflow_confirm_design",
                     "不要逐字符计数", "用户原文", "queued是提交时快照",
                     "pending_confirmation", "用户明确同意", "不代表合格候选或科学签收"):
        assert required in text


def test_tools_list_is_self_contained_when_client_discards_initialize_instructions():
    tools = discover(application(), owner(), "tools/list")["tools"]
    by_name = {tool["name"]: tool for tool in tools}
    assert set(by_name) == {"workflow_submit_sequence", "workflow_check", "workflow_confirm_design"}
    submit = by_name["workflow_submit_sequence"]
    check = by_name["workflow_check"]
    confirm = by_name["workflow_confirm_design"]
    assert "不要逐字符计数" in submit["description"]
    assert "字符和长度由后端校验" in submit["description"]
    assert "workflow_check" in submit["description"]
    assert "workflow.check" not in submit["description"]
    assert "sequence_length" in submit["description"]
    assert "不能用提交工具代替查询" in check["description"]
    assert "pending_confirmation" in check["description"]
    assert "primaryAttachmentId" in check["description"]
    assert "用户明确同意" in confirm["description"]
    assert "未决定时不调用" in confirm["description"]
    assert "后端" in submit["inputSchema"]["properties"]["protein_sequence"]["description"]
    assert "宿主原文" in submit["inputSchema"]["properties"]["host_species"]["description"]


@pytest.mark.parametrize("integration", [False, True])
def test_operator_discovery_keeps_its_distinct_tools_and_instructions(integration):
    app = application() if integration else MCPApplication(NoExecutionService())
    principal = owner("operator-test")
    init = discover(app, principal, "initialize")
    listed = discover(app, principal, "tools/list")
    assert init["instructions"] == "Authenticated engineering workflow service. Scientific Gate remains closed."
    assert all(t["name"].startswith(app.TOOL_PREFIX) for t in listed["tools"])
    assert len(listed["tools"]) == 8


def test_guide_does_not_grant_submit_scope_or_expose_operator_tools():
    app = application()
    for name in ("workflow_submit_sequence", "workflow_confirm_design"):
        schema = next(t for t in app.himat_tools() if t["name"] == name)["inputSchema"]
        # Scope rejection must happen before any adapter or service method runs.
        result = discover(app, owner(), "tools/call", {
            "name": name, "arguments": dict.fromkeys(schema["required"], "untrusted"),
        })
        assert result["isError"]
        assert result["structuredContent"]["error"]["code"] == "FORBIDDEN"
    _, reply = app.dispatch(owner(), {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": app.TOOL_PREFIX + "workflow.submit", "arguments": {}}})
    assert reply["error"]["code"] == -32602
