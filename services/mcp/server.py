"""Standard Model Context Protocol (MCP) server for GridLens.

Exposes deterministic domain tools:
1. verify_claims: Audits candidate claims against evidence with SI unit awareness.
2. check_sufficiency: Evaluates evidence sufficiency against investigation policies.
3. analyze_symmetrical_components: Classifies fault types using Fortescue symmetrical components.

Operates over JSON-RPC 2.0 (stdio or programmatic).
"""
import sys
import json
from typing import Dict, Any
from domain.claims.models import Claim
from domain.evidence.models import Evidence
from domain.investigation.models import InvestigationType
from services.agent.verifier import ClaimVerifier
from services.agent.sufficiency import SufficiencyPolicyEngine
from services.physics.symmetrical import classify_from_phasors, phasor


SERVER_NAME = "gridlens-mcp-server"
SERVER_VERSION = "1.0.0"
DEFAULT_NUMERICAL_TOLERANCE_PERCENT = 0.5

TOOL_DEFINITIONS = [
    {
        "name": "verify_claims",
        "description": "Deterministic claim verifier checking candidate claims against authoritative evidence with SI unit awareness and derived quantity cross-checks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "candidate_claims": {
                    "type": "array",
                    "description": "List of claim objects with claim_id, statement, claim_type (FACT/INFERENCE), and evidence_ids.",
                    "items": {"type": "object"},
                },
                "evidence_list": {
                    "type": "array",
                    "description": "Authoritative evidence objects with evidence_id, fact, structured_value, and unit.",
                    "items": {"type": "object"},
                },
                "numerical_tolerance_percent": {
                    "type": "number",
                    "description": "Allowed numerical error percentage (default 0.5).",
                    "default": DEFAULT_NUMERICAL_TOLERANCE_PERCENT,
                },
            },
            "required": ["candidate_claims", "evidence_list"],
        },
    },
    {
        "name": "check_sufficiency",
        "description": "Evaluates contextual evidence sufficiency against inquiry policies (e.g. PROTECTION_EVENT_INVESTIGATION).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "investigation_type": {
                    "type": "string",
                    "description": "Type of investigation (PROTECTION_EVENT_INVESTIGATION, TOPOLOGY_INQUIRY, CONFIGURATION_VALIDATION, etc.).",
                    "default": "PROTECTION_EVENT_INVESTIGATION",
                },
                "evidence_list": {
                    "type": "array",
                    "description": "List of evidence objects retrieved so far.",
                    "items": {"type": "object"},
                },
            },
            "required": ["evidence_list"],
        },
    },
    {
        "name": "analyze_symmetrical_components",
        "description": "Deterministic Fortescue symmetrical-components fault classifier (Ia, Ib, Ic phasors -> I0, I1, I2, unbalance ratio, fault type).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ia_mag": {"type": "number", "description": "Phase A RMS magnitude in Amps."},
                "ia_ang": {"type": "number", "description": "Phase A angle in degrees."},
                "ib_mag": {"type": "number", "description": "Phase B RMS magnitude in Amps."},
                "ib_ang": {"type": "number", "description": "Phase B angle in degrees."},
                "ic_mag": {"type": "number", "description": "Phase C RMS magnitude in Amps."},
                "ic_ang": {"type": "number", "description": "Phase C angle in degrees."},
                "pickup_threshold_a": {"type": "number", "description": "Overcurrent pickup threshold (default 2500.0).", "default": 2500.0},
            },
            "required": ["ia_mag", "ia_ang", "ib_mag", "ib_ang", "ic_mag", "ic_ang"],
        },
    },
]


class GridLensMCPServer:
    """Core server handling JSON-RPC 2.0 MCP requests."""

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                },
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOL_DEFINITIONS},
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            try:
                result_data = self._dispatch_tool(tool_name, arguments)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(result_data, indent=2)}],
                        "isError": False,
                    },
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Error executing tool '{tool_name}': {str(e)}"}],
                        "isError": True,
                    },
                }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method '{method}' not found"},
            }

    def _dispatch_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "verify_claims":
            claims_raw = args.get("candidate_claims", [])
            ev_raw = args.get("evidence_list", [])
            tol = float(args.get("numerical_tolerance_percent", DEFAULT_NUMERICAL_TOLERANCE_PERCENT))

            claims = [Claim.model_validate(c) for c in claims_raw]
            evs = [Evidence.model_validate(e) for e in ev_raw]

            v_facts, s_infs, r_claims = ClaimVerifier.verify_candidate_claims(
                claims, evs, numerical_tolerance_percent=tol
            )
            return {
                "verified_facts": [c.model_dump() for c in v_facts],
                "supported_inferences": [c.model_dump() for c in s_infs],
                "rejected_claims": [c.model_dump() for c in r_claims],
            }

        elif tool_name == "check_sufficiency":
            inv_type_str = args.get("investigation_type", "PROTECTION_EVENT_INVESTIGATION")
            try:
                inv_type = InvestigationType(inv_type_str)
            except ValueError:
                inv_type = InvestigationType.PROTECTION_EVENT_INVESTIGATION

            ev_raw = args.get("evidence_list", [])
            evs = [Evidence.model_validate(e) for e in ev_raw]

            is_suff, reason, missing = SufficiencyPolicyEngine.evaluate_sufficiency(inv_type, evs)
            return {
                "is_sufficient": is_suff,
                "reason": reason,
                "missing_evidence": missing,
            }

        elif tool_name == "analyze_symmetrical_components":
            ia_mag = float(args["ia_mag"])
            ia_ang = float(args["ia_ang"])
            ib_mag = float(args["ib_mag"])
            ib_ang = float(args["ib_ang"])
            ic_mag = float(args["ic_mag"])
            ic_ang = float(args["ic_ang"])
            pickup = float(args.get("pickup_threshold_a", 2500.0))

            ia = phasor(ia_mag, ia_ang)
            ib = phasor(ib_mag, ib_ang)
            ic = phasor(ic_mag, ic_ang)
            res = classify_from_phasors(ia, ib, ic, pickup_a=pickup)
            return res.model_dump()

        else:
            raise ValueError(f"Unknown tool name '{tool_name}'")


def run_stdio_server():
    """Runs the MCP server reading from stdin and writing to stdout."""
    server = GridLensMCPServer()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = server.handle_request(req)
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {str(e)}"},
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    run_stdio_server()
