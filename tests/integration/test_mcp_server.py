"""Integration test for GridLens Model Context Protocol (MCP) Server."""
import json
import pytest
from unittest.mock import patch
from services.mcp.server import GridLensMCPServer
from services.mcp.server import TOOL_DEFINITIONS
from services.agent.verifier import ClaimVerifier


@pytest.fixture
def mcp_server():
    return GridLensMCPServer()


def test_mcp_server_initialize(mcp_server):
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"clientInfo": {"name": "test-client", "version": "1.0"}},
    }
    resp = mcp_server.handle_request(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert "result" in resp
    assert resp["result"]["serverInfo"]["name"] == "gridlens-mcp-server"
    assert "tools" in resp["result"]["capabilities"]


def test_mcp_server_tools_list(mcp_server):
    req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    resp = mcp_server.handle_request(req)
    assert resp["id"] == 2
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "verify_claims" in tool_names
    assert "check_sufficiency" in tool_names
    assert "analyze_symmetrical_components" in tool_names


def test_mcp_schema_advertises_dispatched_verifier_tolerance(mcp_server):
    """The MCP contract must advertise the same default it dispatches."""
    verify_tool = next(tool for tool in TOOL_DEFINITIONS if tool["name"] == "verify_claims")
    advertised = verify_tool["inputSchema"]["properties"]["numerical_tolerance_percent"]["default"]

    with patch.object(ClaimVerifier, "verify_candidate_claims", return_value=([], [], [])) as verify:
        mcp_server._dispatch_tool("verify_claims", {"candidate_claims": [], "evidence_list": []})

    dispatched = verify.call_args.kwargs["numerical_tolerance_percent"]
    assert advertised == dispatched == 0.5


def test_mcp_server_verify_claims_tool_call(mcp_server):
    ev = {
        "evidence_id": "EV_RMS_1",
        "kind": "CHANNEL_RMS",
        "source_type": "COMTRADE",
        "source_id": "INC-001.DAT",
        "tool_name": "WaveformTool",
        "fact": "Channel IC measured Fault RMS: 3758.63 A.",
        "structured_value": 3758.63,
        "unit": "A",
        "provenance": "RMS",
        "deterministic": True,
    }
    claim = {
        "claim_id": "C1",
        "statement": "Channel IC measured Fault RMS: 3.75863 kA.",  # Unit-aware prefix
        "claim_type": "FACT",
        "evidence_ids": ["EV_RMS_1"],
    }

    req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "verify_claims",
            "arguments": {
                "candidate_claims": [claim],
                "evidence_list": [ev],
                "numerical_tolerance_percent": 0.5,
            },
        },
    }

    resp = mcp_server.handle_request(req)
    assert resp["id"] == 3
    assert resp["result"]["isError"] is False
    content_text = resp["result"]["content"][0]["text"]
    data = json.loads(content_text)
    assert len(data["verified_facts"]) == 1
    assert data["verified_facts"][0]["claim_id"] == "C1"
    assert len(data["rejected_claims"]) == 0


def test_mcp_server_check_sufficiency_tool_call(mcp_server):
    ev = {
        "evidence_id": "EV_TRUNC",
        "kind": "RECORDING_TRUNCATED",
        "source_type": "COMTRADE",
        "source_id": "INC-TRUNC.DAT",
        "tool_name": "WaveformTool",
        "fact": "Truncated",
        "structured_value": True,
        "provenance": "Header",
        "deterministic": True,
    }

    req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "check_sufficiency",
            "arguments": {
                "investigation_type": "PROTECTION_EVENT_INVESTIGATION",
                "evidence_list": [ev],
            },
        },
    }

    resp = mcp_server.handle_request(req)
    assert resp["id"] == 4
    assert resp["result"]["isError"] is False
    data = json.loads(resp["result"]["content"][0]["text"])
    assert data["is_sufficient"] is False
    assert len(data["missing_evidence"]) > 0


def test_mcp_server_symmetrical_components_tool_call(mcp_server):
    # Phase C SLG fault: Ia=240, Ib=240, Ic=3758
    req = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "analyze_symmetrical_components",
            "arguments": {
                "ia_mag": 240.0,
                "ia_ang": 0.0,
                "ib_mag": 240.0,
                "ib_ang": -120.0,
                "ic_mag": 3758.63,
                "ic_ang": 120.0,
                "pickup_threshold_a": 2500.0,
            },
        },
    }

    resp = mcp_server.handle_request(req)
    assert resp["id"] == 5
    assert resp["result"]["isError"] is False
    data = json.loads(resp["result"]["content"][0]["text"])
    assert data["faulted_phase"] == "C"
    assert "LG" in data["fault_type"] or "C" in data["fault_type"]
    assert data["i0_mag"] > 0
