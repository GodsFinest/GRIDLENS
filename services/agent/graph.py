"""Stateful LangGraph investigation orchestrator coordinating deterministic tools and claim verification."""
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, TypedDict, Callable
from pydantic import BaseModel, Field

from domain.investigation.models import (
    InvestigationRequest,
    InvestigationResult,
    InvestigationType,
    AuditTraceEntry,
)
from domain.claims.models import Claim, ClaimType, ConflictLifecycle, ConflictTracker, ConflictTransition
from domain.evidence.models import Evidence, EvidenceKind
from domain.evidence.assessment import EvidenceAssessment
from domain.hypotheses.models import Hypothesis
from domain.models.results import RetrievedDocumentChunk

from services.tools.topology_tool import TopologyTool
from services.tools.waveform_tool import WaveformTool
from services.tools.physics_tool import PhysicsTool
from services.tools.validation_tool import ValidationTool
from services.tools.soe_tool import SOETool
from services.tools.retrieval_tool import RetrievalTool
from services.tools.history_tool import HistoryTool

from services.agent.evidence_factory import EvidenceFactory
from services.agent.assessments import EvidenceAssessor
from services.agent.hypotheses import HypothesisEngine
from services.agent.sufficiency import SufficiencyPolicyEngine
from services.agent.claims import ClaimConstructor
from services.agent.verifier import ClaimVerifier
from services.agent.report_generator import ReportGenerator
from services.agent.resolver import ChannelMappingResolver
from services.safety.sanitizer import InputSanitizer

try:
    from langgraph.graph import END, START, StateGraph
except ImportError:
    END = START = StateGraph = None


class InvestigationGraphState(TypedDict, total=False):
    request: InvestigationRequest
    incident_data: Optional[Dict[str, Any]]
    investigation_id: str
    incident_id: Optional[str]
    user_query: str
    user_role: str
    feeder_id: str
    bay_id: str
    ied_id: str
    declared_channel_map: Optional[Dict[str, str]]
    commissioned_channel_map: Optional[Dict[str, str]]
    investigation_type: InvestigationType
    selected_tools: List[str]
    executed_tools: List[str]
    raw_tool_results: Dict[str, Any]
    evidence_ledger: List[Evidence]
    evidence_assessments: List[EvidenceAssessment]
    hypotheses: List[Hypothesis]
    conflict_tracker: ConflictTracker
    conflict_lifecycle: ConflictLifecycle
    conflict_explanation: Optional[str]
    conflict_transitions: List[ConflictTransition]
    is_sufficient: bool
    sufficiency_reason: str
    missing_evidence: List[str]
    candidate_claims: List[Claim]
    verified_facts: List[Claim]
    supported_inferences: List[Claim]
    rejected_claims: List[Claim]
    citations: List[RetrievedDocumentChunk]
    final_result: Optional[InvestigationResult]
    execution_trace: List[AuditTraceEntry]
    start_time: float


def _trace_stage(stage_name: str, tool_name: Optional[str] = None):
    """Decorator recording physical execution trace with timing and summaries."""
    def decorator(func: Callable):
        async def wrapper(self, state: InvestigationGraphState) -> InvestigationGraphState:
            t0 = time.time()
            step_idx = len(state.get("execution_trace", [])) + 1
            inputs = {
                "investigation_id": state.get("investigation_id"),
                "investigation_type": state.get("investigation_type", InvestigationType.PROTECTION_EVENT_INVESTIGATION).value,
                "feeder_id": state.get("feeder_id"),
            }
            if tool_name:
                inputs["tool"] = tool_name

            # Execute node
            out_state = await func(self, state)
            duration_ms = round((time.time() - t0) * 1000, 2)

            # Build summary
            summary = f"Completed {stage_name}"
            if tool_name:
                summary = f"Executed {tool_name} with {len(out_state.get('evidence_ledger', []))} total facts in ledger"
            elif stage_name == "ASSESS_EVIDENCE":
                summary = f"Assessed {len(out_state.get('evidence_assessments', []))} relationships across {len(out_state.get('hypotheses', []))} hypotheses"
            elif stage_name == "RESOLVE_CONFLICTS":
                summary = f"Conflict lifecycle state: {out_state.get('conflict_lifecycle', ConflictLifecycle.NO_CONFLICT).value}"
            elif stage_name == "SUFFICIENCY_GATE":
                summary = f"Sufficient: {out_state.get('is_sufficient')}. Missing: {len(out_state.get('missing_evidence', []))}"
            elif stage_name == "CONSTRUCT_CLAIMS":
                summary = f"Constructed {len(out_state.get('candidate_claims', []))} candidate claims"
            elif stage_name == "VERIFY_CLAIMS":
                summary = f"Verified {len(out_state.get('verified_facts', []))} facts, {len(out_state.get('supported_inferences', []))} inferences"
            elif stage_name == "ABSTAIN":
                summary = f"Abstention issued: {out_state.get('sufficiency_reason', '')[:60]}"

            entry = AuditTraceEntry(
                step_index=step_idx,
                timestamp=datetime.now(timezone.utc).isoformat(),
                stage=stage_name,
                tool_invoked=tool_name,
                inputs=inputs,
                outputs_summary=summary,
                duration_ms=duration_ms,
            )
            out_state.setdefault("execution_trace", []).append(entry)
            if out_state.get("final_result"):
                out_state["final_result"].execution_trace = list(out_state["execution_trace"])
            return out_state
        return wrapper
    return decorator


class GridLensInvestigationWorkflow:
    """The canonical stateful agent orchestrator for electrical protection investigations."""

    def __init__(
        self,
        topology_tool: Optional[TopologyTool] = None,
        waveform_tool: Optional[WaveformTool] = None,
        physics_tool: Optional[PhysicsTool] = None,
        validation_tool: Optional[ValidationTool] = None,
        soe_tool: Optional[SOETool] = None,
        retrieval_tool: Optional[RetrievalTool] = None,
        history_tool: Optional[HistoryTool] = None,
        report_generator: Optional[ReportGenerator] = None,
        llm_provider: Optional[Any] = None,
    ):
        self.topology_tool = topology_tool or TopologyTool()
        self.waveform_tool = waveform_tool or WaveformTool()
        self.physics_tool = physics_tool or PhysicsTool()
        self.validation_tool = validation_tool or ValidationTool()
        self.soe_tool = soe_tool or SOETool()
        self.retrieval_tool = retrieval_tool or RetrievalTool()
        self.history_tool = history_tool or HistoryTool()
        self.report_generator = report_generator or ReportGenerator(llm_provider=llm_provider)
        self._compiled_graph = self._build_langgraph()

    def _build_langgraph(self):
        """Build the load-bearing compiled LangGraph state graph."""
        if StateGraph is None:
            return None

        graph = StateGraph(InvestigationGraphState)

        # Register operational nodes
        graph.add_node("classify", self._node_classify)
        graph.add_node("run_topology", self._node_run_topology)
        graph.add_node("run_waveform", self._node_run_waveform)
        graph.add_node("run_physics", self._node_run_physics)
        graph.add_node("run_validation", self._node_run_validation)
        graph.add_node("run_soe", self._node_run_soe)
        graph.add_node("run_retrieval", self._node_run_retrieval)
        graph.add_node("run_history", self._node_run_history)
        graph.add_node("assess", self._node_assess)
        graph.add_node("resolve_conflicts", self._node_resolve_conflicts)
        graph.add_node("sufficiency_gate", self._node_sufficiency_gate)
        graph.add_node("abstain", self._node_abstain)
        graph.add_node("construct_claims", self._node_construct_claims)
        graph.add_node("verify", self._node_verify)
        graph.add_node("synthesize_report", self._node_synthesize_report)

        # Start edge
        graph.add_edge(START, "classify")

        # Routing based on investigation type
        def route_by_type(state: InvestigationGraphState) -> str:
            inv_type = state.get("investigation_type", InvestigationType.PROTECTION_EVENT_INVESTIGATION)
            if inv_type == InvestigationType.TOPOLOGY_INQUIRY:
                return "topo_start"
            elif inv_type == InvestigationType.DOCUMENTATION_QA:
                return "doc_start"
            elif inv_type == InvestigationType.CONFIGURATION_VALIDATION:
                return "cfg_start"
            elif inv_type == InvestigationType.EVENT_TIMELINE_RECONCILIATION:
                return "soe_start"
            else:
                return "event_start"

        graph.add_conditional_edges(
            "classify",
            route_by_type,
            {
                "topo_start": "run_topology",
                "doc_start": "run_retrieval",
                "cfg_start": "run_topology",
                "soe_start": "run_topology",
                "event_start": "run_topology",
            },
        )

        # Tool chaining per type
        # For TOPOLOGY_INQUIRY: run_topology -> assess
        # For CONFIGURATION_VALIDATION: run_topology -> run_validation -> assess
        # For EVENT_TIMELINE_RECONCILIATION: run_topology -> run_soe -> assess
        # For PROTECTION_EVENT_INVESTIGATION: run_topology -> run_waveform -> run_physics -> run_validation -> run_soe -> run_retrieval -> run_history -> assess
        def after_topology(state: InvestigationGraphState) -> str:
            inv_type = state.get("investigation_type")
            if inv_type == InvestigationType.TOPOLOGY_INQUIRY:
                return "assess"
            elif inv_type == InvestigationType.CONFIGURATION_VALIDATION:
                return "run_validation"
            elif inv_type == InvestigationType.EVENT_TIMELINE_RECONCILIATION:
                return "run_soe"
            else:
                return "run_waveform"

        graph.add_conditional_edges(
            "run_topology",
            after_topology,
            {
                "assess": "assess",
                "run_validation": "run_validation",
                "run_soe": "run_soe",
                "run_waveform": "run_waveform",
            },
        )

        # Protection Event pipeline chain
        graph.add_edge("run_waveform", "run_physics")
        graph.add_edge("run_physics", "run_validation")

        def after_validation(state: InvestigationGraphState) -> str:
            inv_type = state.get("investigation_type")
            if inv_type == InvestigationType.CONFIGURATION_VALIDATION:
                return "assess"
            return "run_soe"

        graph.add_conditional_edges(
            "run_validation",
            after_validation,
            {"assess": "assess", "run_soe": "run_soe"},
        )

        def after_soe(state: InvestigationGraphState) -> str:
            inv_type = state.get("investigation_type")
            if inv_type == InvestigationType.EVENT_TIMELINE_RECONCILIATION:
                return "assess"
            return "run_retrieval"

        graph.add_conditional_edges(
            "run_soe",
            after_soe,
            {"assess": "assess", "run_retrieval": "run_retrieval"},
        )

        # Retrieval can go to run_history (for event) or assess (for doc QA)
        def after_retrieval(state: InvestigationGraphState) -> str:
            inv_type = state.get("investigation_type")
            if inv_type == InvestigationType.DOCUMENTATION_QA:
                return "assess"
            return "run_history"

        graph.add_conditional_edges(
            "run_retrieval",
            after_retrieval,
            {"assess": "assess", "run_history": "run_history"},
        )

        graph.add_edge("run_history", "assess")

        # After assess -> resolve_conflicts -> sufficiency_gate
        graph.add_edge("assess", "resolve_conflicts")
        graph.add_edge("resolve_conflicts", "sufficiency_gate")

        # Conditional edge from sufficiency_gate
        def route_sufficiency(state: InvestigationGraphState) -> str:
            if not state.get("is_sufficient", True):
                return "abstain"
            return "construct_claims"

        graph.add_conditional_edges(
            "sufficiency_gate",
            route_sufficiency,
            {
                "abstain": "abstain",
                "construct_claims": "construct_claims",
            },
        )

        graph.add_edge("abstain", END)
        graph.add_edge("construct_claims", "verify")
        graph.add_edge("verify", "synthesize_report")
        graph.add_edge("synthesize_report", END)

        return graph.compile()

    # Node Implementations
    @_trace_stage("INTENT_CLASSIFICATION_AND_TOOL_SELECTION")
    async def _node_classify(self, state: InvestigationGraphState) -> InvestigationGraphState:
        req = state["request"]
        inv_type, selected_tools = self.classify_query_intent(req.user_query)

        # Discover incident from seed data or request
        incident = self._resolve_incident(req, state.get("incident_data"))

        # For TOPOLOGY_INQUIRY, target equipment takes precedence over incident context
        target_eq = req.target_equipment_id
        if not target_eq and "F13" in req.user_query.upper():
            target_eq = "F13"
        elif not target_eq and "F12" in req.user_query.upper():
            target_eq = "F12"

        if inv_type == InvestigationType.TOPOLOGY_INQUIRY and target_eq:
            feeder_id = target_eq
            bay_id = f"BAY_{feeder_id}"
            ied_id = f"IED_{feeder_id.replace('F', '')}"
            declared_map = self.topology_tool.graph_repo.get_declared_channel_mapping(ied_id)
            comm_map = self.topology_tool.graph_repo.get_commissioned_channel_mapping(ied_id)
        else:
            feeder_id = (incident.get("feeder_id") if incident else None) or req.target_equipment_id or "F12"
            bay_id = (incident.get("bay_id") if incident else None) or f"BAY_{feeder_id}"
            ied_id = (incident.get("involved_ied_id") if incident else None) or f"IED_{feeder_id.replace('F', '')}"
            declared_map = (incident.get("declared_channel_phase_map") if incident else None) or self.topology_tool.graph_repo.get_declared_channel_mapping(ied_id)
            comm_map = self.topology_tool.graph_repo.get_commissioned_channel_mapping(ied_id)

        state["incident_id"] = req.incident_id or (incident.get("incident_id") if incident else None)
        state["feeder_id"] = feeder_id
        state["bay_id"] = bay_id
        state["ied_id"] = ied_id
        state["declared_channel_map"] = declared_map
        state["commissioned_channel_map"] = comm_map
        state["investigation_type"] = inv_type
        state["selected_tools"] = selected_tools
        state["incident_data"] = incident
        return state

    @_trace_stage("TOPOLOGY_EXTRACTION", "TopologyTool")
    async def _node_run_topology(self, state: InvestigationGraphState) -> InvestigationGraphState:
        topo_res = await self.topology_tool.execute(state["feeder_id"])
        state.setdefault("raw_tool_results", {})["TopologyTool"] = topo_res
        evs = EvidenceFactory.from_topology(topo_res)
        state.setdefault("evidence_ledger", []).extend(evs)
        state.setdefault("executed_tools", []).append("TopologyTool")
        return state

    @_trace_stage("WAVEFORM_ANALYSIS", "WaveformTool")
    async def _node_run_waveform(self, state: InvestigationGraphState) -> InvestigationGraphState:
        inc = state.get("incident_data")
        file_id = (inc.get("comtrade_file_id") if inc else None) or state.get("incident_id") or "INC-2026-001"
        pickup = (inc or {}).get("pickup_threshold_a", 2500.0)
        comtrade_res = await self.waveform_tool.execute(file_id, pickup_threshold_a=pickup)
        state.setdefault("raw_tool_results", {})["WaveformTool"] = comtrade_res
        evs = EvidenceFactory.from_comtrade(comtrade_res)
        state.setdefault("evidence_ledger", []).extend(evs)
        state.setdefault("executed_tools", []).append("WaveformTool")
        return state

    @_trace_stage("PHYSICS_ANALYSIS", "PhysicsTool")
    async def _node_run_physics(self, state: InvestigationGraphState) -> InvestigationGraphState:
        """Agent-invoked protection analysis on measured waveform data.

        Runs symmetrical-components classification plus a pickup-setting
        sanity check. Fails closed (SKIPPED result, no evidence) on
        truncated/missing waveforms so Incident C still abstains cleanly.
        """
        from services.tools.physics_tool import PhysicsAnalysisResult

        comtrade_res = state.get("raw_tool_results", {}).get("WaveformTool")
        inc = state.get("incident_data") or {}
        incident_id = state.get("incident_id") or inc.get("incident_id") or "INC-2026-001"
        feeder_id = state.get("feeder_id", "F12")

        phase_rms: Dict[str, float] = {}
        pickup_a = 2500.0
        if comtrade_res is not None and not comtrade_res.is_truncated:
            pickup_a = comtrade_res.pickup_threshold_a or 2500.0
            for ch_name, m in (comtrade_res.analog_measurements or {}).items():
                unit = (m.unit or "").upper()
                is_current = unit in ("A", "AMPS", "KA") or ch_name.upper().startswith("I")
                if not is_current:
                    continue
                letter = (m.phase or "").strip().upper()
                if letter not in ("A", "B", "C"):
                    tail = ch_name.strip().upper()[-1] if ch_name else ""
                    letter = tail if tail in ("A", "B", "C") else ""
                if letter in ("A", "B", "C"):
                    val = float(m.fault_rms)
                    if unit == "KA":
                        val *= 1000.0
                    phase_rms.setdefault(letter, val)

        max_load_a: Optional[float] = None
        time_dial = 0.1
        repo = getattr(self.topology_tool, "graph_repo", None)
        graph_obj = getattr(repo, "graph", None)
        if graph_obj is not None:
            feeder_node = graph_obj.get_node(feeder_id)
            if feeder_node is not None:
                try:
                    max_load_a = float(feeder_node.attributes.get("rated_continuous_load_a"))
                except (TypeError, ValueError):
                    max_load_a = None
            topo_res = state.get("raw_tool_results", {}).get("TopologyTool")
            relay_id = getattr(topo_res, "primary_relay_id", None) if topo_res else None
            if relay_id:
                relay_node = graph_obj.get_node(relay_id)
                if relay_node is not None:
                    try:
                        time_dial = float(relay_node.attributes.get("time_dial", 0.1))
                    except (TypeError, ValueError):
                        time_dial = 0.1

        if comtrade_res is None or comtrade_res.is_truncated or len(phase_rms) < 3:
            phys_res = PhysicsAnalysisResult(
                incident_id=incident_id,
                feeder_id=feeder_id,
                classification_basis="SKIPPED",
                skip_reason="Waveform truncated/missing or fewer than three current phases; no classification attempted.",
                setting_check_skipped_reason="Classification skipped.",
            )
        else:
            phys_res = await self.physics_tool.execute_symmetrical(
                incident_id=incident_id,
                feeder_id=feeder_id,
                phase_rms=phase_rms,
                pickup_a=pickup_a,
                max_load_a=max_load_a,
                time_dial=time_dial,
            )
        state.setdefault("raw_tool_results", {})["PhysicsTool"] = phys_res
        state.setdefault("evidence_ledger", []).extend(EvidenceFactory.from_physics(phys_res))
        state.setdefault("executed_tools", []).append("PhysicsTool")
        return state

    @_trace_stage("CONFIGURATION_VALIDATION", "ValidationTool")
    async def _node_run_validation(self, state: InvestigationGraphState) -> InvestigationGraphState:
        val_res = await self.validation_tool.execute(
            bay_id=state["bay_id"],
            feeder_id=state["feeder_id"],
            ied_id=state["ied_id"],
            custom_mapping=state.get("declared_channel_map"),
        )
        state.setdefault("raw_tool_results", {})["ValidationTool"] = val_res
        evs = EvidenceFactory.from_validation(val_res)
        state.setdefault("evidence_ledger", []).extend(evs)
        state.setdefault("executed_tools", []).append("ValidationTool")
        return state

    @_trace_stage("TIMELINE_RECONCILIATION", "SOETool")
    async def _node_run_soe(self, state: InvestigationGraphState) -> InvestigationGraphState:
        inc = state.get("incident_data")
        inc_id = state.get("incident_id") or (inc.get("incident_id") if inc else "INC-2026-001")
        events = inc.get("events", []) if inc else []
        comtrade_res = state.get("raw_tool_results", {}).get("WaveformTool")
        t0 = comtrade_res.onset_time_ms if comtrade_res else None
        dt = comtrade_res.digital_transitions if comtrade_res else None
        soe_res = await self.soe_tool.execute(
            incident_id=inc_id,
            events=events,
            comtrade_digital_transitions=dt,
            disturbance_t0_ms=t0,
        )
        state.setdefault("raw_tool_results", {})["SOETool"] = soe_res
        evs = EvidenceFactory.from_timeline(soe_res)
        state.setdefault("evidence_ledger", []).extend(evs)
        state.setdefault("executed_tools", []).append("SOETool")
        return state

    @_trace_stage("DOCUMENT_RETRIEVAL", "RetrievalTool")
    async def _node_run_retrieval(self, state: InvestigationGraphState) -> InvestigationGraphState:
        docs_res = await self.retrieval_tool.execute(query=state["user_query"])
        state.setdefault("raw_tool_results", {})["RetrievalTool"] = docs_res
        evs = EvidenceFactory.from_documents(docs_res)
        state.setdefault("evidence_ledger", []).extend(evs)
        state["citations"] = docs_res.chunks
        state.setdefault("executed_tools", []).append("RetrievalTool")
        return state

    @_trace_stage("HISTORY_CORRELATION", "HistoryTool")
    async def _node_run_history(self, state: InvestigationGraphState) -> InvestigationGraphState:
        hist_res = await self.history_tool.execute(feeder_id=state["feeder_id"])
        state.setdefault("raw_tool_results", {})["HistoryTool"] = hist_res
        evs = EvidenceFactory.from_history(hist_res)
        state.setdefault("evidence_ledger", []).extend(evs)
        state.setdefault("executed_tools", []).append("HistoryTool")
        return state

    @_trace_stage("ASSESS_EVIDENCE")
    async def _node_assess(self, state: InvestigationGraphState) -> InvestigationGraphState:
        assessments = EvidenceAssessor.assess_evidence_for_hypotheses(state["evidence_ledger"])
        hypotheses = HypothesisEngine.evaluate_hypotheses(state["evidence_ledger"], assessments)
        state["evidence_assessments"] = assessments
        state["hypotheses"] = hypotheses
        return state

    @_trace_stage("RESOLVE_CONFLICTS")
    async def _node_resolve_conflicts(self, state: InvestigationGraphState) -> InvestigationGraphState:
        tracker = state.get("conflict_tracker") or ConflictTracker()
        state["conflict_tracker"] = tracker

        is_resolved, reconciling_map, rule_id = await ChannelMappingResolver.resolve_cross_source_conflict(
            evidence_list=state["evidence_ledger"],
            bay_id=state["bay_id"],
            validator=self.validation_tool.validator,
            conflict_tracker=tracker,
            declared_mapping=state.get("declared_channel_map"),
            commissioned_mapping=state.get("commissioned_channel_map"),
        )

        state["conflict_lifecycle"] = tracker.current_state
        state["conflict_transitions"] = tracker.transitions

        if tracker.current_state == ConflictLifecycle.CONFLICT_RESOLVED:
            state["conflict_explanation"] = f"Resolved via {rule_id}: physical wiring inversion verified."
            # Re-evaluate assessments to ensure H3 is top scored
            assessments = EvidenceAssessor.assess_evidence_for_hypotheses(state["evidence_ledger"])
            hypotheses = HypothesisEngine.evaluate_hypotheses(state["evidence_ledger"], assessments)
            state["evidence_assessments"] = assessments
            state["hypotheses"] = hypotheses
        elif tracker.current_state == ConflictLifecycle.CONFLICT_UNRESOLVED:
            state["conflict_explanation"] = "Unresolvable contradiction between protective relay flags and physical oscillography."
            state["is_sufficient"] = False

        return state

    @_trace_stage("SUFFICIENCY_GATE")
    async def _node_sufficiency_gate(self, state: InvestigationGraphState) -> InvestigationGraphState:
        top_hyp = state["hypotheses"][0] if state.get("hypotheses") else Hypothesis(
            hypothesis_id="H6", code="H6", title="Insufficient Evidence",
            category="DATA_QUALITY", root_cause_type="INSUFFICIENT_DATA",
            description="Insufficient evidence to evaluate.",
        )
        is_sufficient, reason, missing = SufficiencyPolicyEngine.evaluate_sufficiency(
            inv_type=state["investigation_type"],
            evidence_list=state["evidence_ledger"],
            top_hypothesis=top_hyp,
            conflict_lifecycle=state.get("conflict_lifecycle", ConflictLifecycle.NO_CONFLICT),
        )
        state["is_sufficient"] = is_sufficient
        state["sufficiency_reason"] = reason
        state["missing_evidence"] = missing
        return state

    @_trace_stage("ABSTAIN")
    async def _node_abstain(self, state: InvestigationGraphState) -> InvestigationGraphState:
        top_hyp = next((h for h in state.get("hypotheses", []) if h.code == "H6"), None)
        if not top_hyp:
            top_hyp = Hypothesis(
                hypothesis_id="H6", code="H6", title="Insufficient Evidence",
                category="DATA_QUALITY", root_cause_type="INSUFFICIENT_DATA",
                description=state.get("sufficiency_reason", "Insufficient data"),
                confidence_normalized=0.05,
            )
            state.setdefault("hypotheses", []).insert(0, top_hyp)
        else:
            # Move H6 to top
            state["hypotheses"].remove(top_hyp)
            state["hypotheses"].insert(0, top_hyp)

        candidate_claims = ClaimConstructor.construct_candidate_claims(
            evidence_list=state["evidence_ledger"],
            hypotheses=state["hypotheses"],
            conflict_lifecycle=state.get("conflict_lifecycle", ConflictLifecycle.NO_CONFLICT),
        )
        v_facts, s_infs, r_claims = ClaimVerifier.verify_candidate_claims(
            candidate_claims=candidate_claims,
            evidence_list=state["evidence_ledger"],
        )

        duration = (time.time() - state["start_time"]) * 1000
        final_res = await self.report_generator.generate_final_report(
            investigation_id=state["investigation_id"],
            incident_id=state.get("incident_id"),
            investigation_type=state["investigation_type"],
            user_query=state["user_query"],
            hypotheses=state["hypotheses"],
            verified_facts=v_facts,
            supported_inferences=s_infs,
            rejected_claims=r_claims,
            is_sufficient=False,
            sufficiency_reason=state.get("sufficiency_reason", "Insufficient evidence"),
            conflict_lifecycle=state.get("conflict_lifecycle", ConflictLifecycle.NO_CONFLICT),
            citations=state.get("citations", []),
            execution_trace=state.get("execution_trace", []),
            start_time_iso=datetime.fromtimestamp(state["start_time"], tz=timezone.utc).isoformat(),
            duration_ms=duration,
            conflict_transitions=state.get("conflict_transitions", []),
            conflict_explanation=state.get("conflict_explanation"),
        )
        state["final_result"] = final_res
        return state

    @_trace_stage("CONSTRUCT_CLAIMS")
    async def _node_construct_claims(self, state: InvestigationGraphState) -> InvestigationGraphState:
        claims = ClaimConstructor.construct_candidate_claims(
            evidence_list=state["evidence_ledger"],
            hypotheses=state["hypotheses"],
            conflict_lifecycle=state.get("conflict_lifecycle", ConflictLifecycle.NO_CONFLICT),
        )
        state["candidate_claims"] = claims
        return state

    @_trace_stage("VERIFY_CLAIMS")
    async def _node_verify(self, state: InvestigationGraphState) -> InvestigationGraphState:
        v_facts, s_infs, r_claims = ClaimVerifier.verify_candidate_claims(
            candidate_claims=state["candidate_claims"],
            evidence_list=state["evidence_ledger"],
        )
        state["verified_facts"] = v_facts
        state["supported_inferences"] = s_infs
        state["rejected_claims"] = r_claims
        return state

    @_trace_stage("SYNTHESIZE_REPORT")
    async def _node_synthesize_report(self, state: InvestigationGraphState) -> InvestigationGraphState:
        duration = (time.time() - state["start_time"]) * 1000
        final_res = await self.report_generator.generate_final_report(
            investigation_id=state["investigation_id"],
            incident_id=state.get("incident_id"),
            investigation_type=state["investigation_type"],
            user_query=state["user_query"],
            hypotheses=state["hypotheses"],
            verified_facts=state["verified_facts"],
            supported_inferences=state["supported_inferences"],
            rejected_claims=state["rejected_claims"],
            is_sufficient=state["is_sufficient"],
            sufficiency_reason=state["sufficiency_reason"],
            conflict_lifecycle=state.get("conflict_lifecycle", ConflictLifecycle.NO_CONFLICT),
            citations=state.get("citations", []),
            execution_trace=state.get("execution_trace", []),
            start_time_iso=datetime.fromtimestamp(state["start_time"], tz=timezone.utc).isoformat(),
            duration_ms=duration,
            conflict_transitions=state.get("conflict_transitions", []),
            conflict_explanation=state.get("conflict_explanation"),
        )
        state["final_result"] = final_res
        return state

    # Context Resolution Helper
    @classmethod
    def _resolve_incident(
        cls,
        request: InvestigationRequest,
        incident_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if incident_data:
            return incident_data

        try:
            with open("data/seed/incidents.json", "r", encoding="utf-8") as f:
                incidents = json.load(f)
        except Exception:
            return None

        # By incident_id (case-insensitive, matching the REST router behavior)
        if request.incident_id:
            want = request.incident_id.upper()
            for inc in incidents:
                if str(inc.get("incident_id", "")).upper() == want:
                    return inc

        q_upper = request.user_query.upper()
        # By incident id in query
        for inc in incidents:
            if inc.get("incident_id") in q_upper:
                return inc

        # By target equipment
        if request.target_equipment_id:
            for inc in incidents:
                if inc.get("feeder_id") == request.target_equipment_id:
                    return inc

        # By feeder mention in query
        for inc in incidents:
            f_id = inc.get("feeder_id")
            if f_id and f_id.upper() in q_upper:
                return inc

        return incidents[0] if incidents else None

    @classmethod
    def classify_query_intent(cls, user_query: str) -> Tuple[InvestigationType, List[str]]:
        q_lower = user_query.lower()

        # 1. Topology Inquiry Check
        if (
            "which relay" in q_lower or
            "which circuit breaker" in q_lower or
            "which breaker" in q_lower or
            "what breaker" in q_lower or
            "protects feeder" in q_lower or
            "associated with feeder" in q_lower or
            "connected to bus" in q_lower or
            "substation topology" in q_lower
        ) and "trip" not in q_lower and "incident" not in q_lower:
            return InvestigationType.TOPOLOGY_INQUIRY, ["TopologyTool"]

        # 2. Documentation / Conceptual QA Check
        if (
            "what does" in q_lower or
            "define" in q_lower or
            "meaning of" in q_lower or
            "explain the operating principle" in q_lower or
            "what is the standard clearing time" in q_lower or
            "what is the function of" in q_lower or
            "how does ansi" in q_lower or
            "sop" in q_lower or
            "iec 61850" in q_lower
        ) and "why did" not in q_lower and "incident" not in q_lower:
            return InvestigationType.DOCUMENTATION_QA, ["RetrievalTool"]

        # 3. Configuration Validation Check
        if "is the configuration" in q_lower or "is configuration valid" in q_lower or "validate bay" in q_lower or "rule check" in q_lower:
            return InvestigationType.CONFIGURATION_VALIDATION, ["TopologyTool", "ValidationTool"]

        # 4. Sequence of Events / Timeline Check
        if "show timeline" in q_lower or "sequence of events" in q_lower or "soe log" in q_lower:
            return InvestigationType.EVENT_TIMELINE_RECONCILIATION, ["SOETool", "TopologyTool"]

        # 5. Default: Full Protection Event Investigation
        return InvestigationType.PROTECTION_EVENT_INVESTIGATION, [
            "TopologyTool", "WaveformTool", "PhysicsTool", "ValidationTool", "SOETool", "RetrievalTool", "HistoryTool"
        ]

    @staticmethod
    def _sanitize_request_query(request: InvestigationRequest) -> tuple[str, bool]:
        """Defense-in-depth input sanitization at the workflow entry point.

        Returns (sanitized_query, injection_detected). Callers on the HTTP hot
        path (routers) already reject with 400 on detection; the workflow layer
        sanitizes and records the detection in the audit trace so direct
        workflow callers (evaluator, tests, MCP) get the same safe behavior.
        Detection here never alters tool logic — the query is treated as DATA.
        """
        raw = request.user_query or ""
        detected = InputSanitizer.detect_injection_attempt(raw)
        clean = InputSanitizer.sanitize_untrusted_data(raw)
        request.user_query = clean
        return clean, detected

    async def run_investigation(
        self,
        request: InvestigationRequest,
        incident_data: Optional[Dict[str, Any]] = None,
    ) -> InvestigationResult:
        """Runs the investigation via the compiled LangGraph execution graph or linear fallback."""
        inv_id = request.investigation_id or f"INV-{uuid.uuid4().hex[:12].upper()}"
        sanitized_query, injection_detected = self._sanitize_request_query(request)
        initial_trace: List[AuditTraceEntry] = []
        if injection_detected:
            initial_trace.append(
                AuditTraceEntry(
                    step_index=1,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    stage="INPUT_SANITIZATION",
                    tool_invoked=None,
                    inputs={"stage": "workflow_entry"},
                    outputs_summary="Prompt-injection signature detected in user_query; input sanitized and treated as DATA (tool logic unchanged).",
                    duration_ms=0.0,
                )
            )
        initial_state: InvestigationGraphState = {
            "request": request,
            "incident_data": incident_data,
            "investigation_id": inv_id,
            "user_query": sanitized_query,
            "user_role": request.user_role,
            "start_time": time.time(),
            "execution_trace": initial_trace,
            "evidence_ledger": [],
            "raw_tool_results": {},
            "executed_tools": [],
            "citations": [],
            "candidate_claims": [],
            "verified_facts": [],
            "supported_inferences": [],
            "rejected_claims": [],
            "missing_evidence": [],
            "conflict_tracker": ConflictTracker(),
            "conflict_lifecycle": ConflictLifecycle.NO_CONFLICT,
            "conflict_transitions": [],
            "is_sufficient": True,
            "sufficiency_reason": "",
        }

        if self._compiled_graph is not None:
            final_state = await self._compiled_graph.ainvoke(initial_state)
            res = final_state["final_result"]
            res._evidence_ledger = final_state.get("evidence_ledger", [])
            return res

        res = await self._run_investigation_linear(initial_state)
        res._evidence_ledger = initial_state.get("evidence_ledger", [])
        return res

    async def stream_investigation(
        self,
        request: InvestigationRequest,
        incident_data: Optional[Dict[str, Any]] = None,
    ):
        """Asynchronously streams step-by-step LangGraph node execution events via StateGraph.astream."""
        inv_id = request.investigation_id or f"INV-{uuid.uuid4().hex[:12].upper()}"
        sanitized_query, injection_detected = self._sanitize_request_query(request)
        initial_trace: List[AuditTraceEntry] = []
        if injection_detected:
            initial_trace.append(
                AuditTraceEntry(
                    step_index=1,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    stage="INPUT_SANITIZATION",
                    tool_invoked=None,
                    inputs={"stage": "workflow_entry"},
                    outputs_summary="Prompt-injection signature detected in user_query; input sanitized and treated as DATA (tool logic unchanged).",
                    duration_ms=0.0,
                )
            )
        initial_state: InvestigationGraphState = {
            "request": request,
            "incident_data": incident_data,
            "investigation_id": inv_id,
            "user_query": sanitized_query,
            "user_role": request.user_role,
            "start_time": time.time(),
            "execution_trace": initial_trace,
            "evidence_ledger": [],
            "raw_tool_results": {},
            "executed_tools": [],
            "citations": [],
            "candidate_claims": [],
            "verified_facts": [],
            "supported_inferences": [],
            "rejected_claims": [],
            "missing_evidence": [],
            "conflict_tracker": ConflictTracker(),
            "conflict_lifecycle": ConflictLifecycle.NO_CONFLICT,
            "conflict_transitions": [],
            "is_sufficient": True,
            "sufficiency_reason": "",
        }

        latest_state = initial_state
        if self._compiled_graph is not None:
            async for chunk in self._compiled_graph.astream(initial_state):
                for node_name, node_state in chunk.items():
                    latest_state = node_state
                    trace_entry = node_state.get("execution_trace", [])[-1] if node_state.get("execution_trace") else None
                    yield {
                        "event": "node_completed",
                        "node": node_name,
                        "stage": trace_entry.stage if trace_entry else node_name.upper(),
                        "tool_invoked": trace_entry.tool_invoked if trace_entry else None,
                        "outputs_summary": trace_entry.outputs_summary if trace_entry else "",
                        "duration_ms": trace_entry.duration_ms if trace_entry else 0.0,
                        "facts_count": len(node_state.get("evidence_ledger", [])),
                    }
            final_res = latest_state.get("final_result")
            yield {
                "event": "investigation_completed",
                "result": final_res,
                "evidence_ledger": latest_state.get("evidence_ledger", []),
            }
        else:
            final_res = await self._run_investigation_linear(initial_state)
            yield {
                "event": "investigation_completed",
                "result": final_res,
                "evidence_ledger": initial_state.get("evidence_ledger", []),
            }

    async def _run_investigation_linear(
        self,
        state: InvestigationGraphState,
    ) -> InvestigationResult:
        """Documented fallback linear execution sequence when langgraph is not installed."""
        state = await self._node_classify(state)
        inv_type = state["investigation_type"]

        if inv_type == InvestigationType.TOPOLOGY_INQUIRY:
            state = await self._node_run_topology(state)
        elif inv_type == InvestigationType.DOCUMENTATION_QA:
            state = await self._node_run_retrieval(state)
        elif inv_type == InvestigationType.CONFIGURATION_VALIDATION:
            state = await self._node_run_topology(state)
            state = await self._node_run_validation(state)
        elif inv_type == InvestigationType.EVENT_TIMELINE_RECONCILIATION:
            state = await self._node_run_topology(state)
            state = await self._node_run_soe(state)
        else:
            state = await self._node_run_topology(state)
            state = await self._node_run_waveform(state)
            state = await self._node_run_physics(state)
            state = await self._node_run_validation(state)
            state = await self._node_run_soe(state)
            state = await self._node_run_retrieval(state)
            state = await self._node_run_history(state)

        state = await self._node_assess(state)
        state = await self._node_resolve_conflicts(state)
        state = await self._node_sufficiency_gate(state)

        if not state.get("is_sufficient", True):
            state = await self._node_abstain(state)
        else:
            state = await self._node_construct_claims(state)
            state = await self._node_verify(state)
            state = await self._node_synthesize_report(state)

        return state["final_result"]
