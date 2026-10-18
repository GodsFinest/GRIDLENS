"""Tests for conflict lifecycle transitions and data-driven resolution."""
import json
import os
import re
from pathlib import Path
import pytest
from domain.investigation.models import InvestigationRequest
from domain.claims.models import ConflictLifecycle
from services.agent.graph import GridLensInvestigationWorkflow


@pytest.mark.asyncio
async def test_incident_b_full_conflict_lifecycle():
    """Verify Incident B undergoes NO_CONFLICT -> CONFLICT_DETECTED -> INVESTIGATION -> CONFLICT_RESOLVED."""
    workflow = GridLensInvestigationWorkflow()
    with open("data/seed/incidents.json", "r", encoding="utf-8") as f:
        incidents = json.load(f)
    inc_b = next(i for i in incidents if i["incident_id"] == "INC-2026-002")

    req = InvestigationRequest(
        incident_id="INC-2026-002",
        user_query="Investigate deceptive phase trip in incident B with conflicting relay flag and waveform.",
    )
    result = await workflow.run_investigation(req, incident_data=inc_b)

    assert result.is_sufficient is True
    assert result.hypotheses[0].code == "H3"
    assert result.conflict_lifecycle == ConflictLifecycle.CONFLICT_RESOLVED

    # The transition order is part of the conflict lifecycle contract.
    transitions = result.conflict_transitions
    assert len(transitions) == 3

    t1, t2, t3 = transitions
    assert t1.from_state == ConflictLifecycle.NO_CONFLICT
    assert t1.to_state == ConflictLifecycle.CONFLICT_DETECTED
    assert t1.rule_id == "RULE-CONFLICT-001"

    assert t2.from_state == ConflictLifecycle.CONFLICT_DETECTED
    assert t2.to_state == ConflictLifecycle.INVESTIGATION
    assert t2.rule_id == "RULE-CONFLICT-INV-001"

    assert t3.from_state == ConflictLifecycle.INVESTIGATION
    assert t3.to_state == ConflictLifecycle.CONFLICT_RESOLVED
    assert t3.rule_id == "RULE-MAP-003"
    assert "CT12C" in t3.explanation or "CH1" in t3.explanation


@pytest.mark.asyncio
async def test_incident_d_unresolvable_conflict_abstains():
    """Verify INC-2026-004 ends in CONFLICT_UNRESOLVED and routes to explicit abstention."""
    workflow = GridLensInvestigationWorkflow()
    with open("data/seed/incidents.json", "r", encoding="utf-8") as f:
        incidents = json.load(f)
    inc_d = next(i for i in incidents if i["incident_id"] == "INC-2026-004")

    req = InvestigationRequest(
        incident_id="INC-2026-004",
        user_query="Why did feeder F12 trip on Phase A when load was steady?",
    )
    result = await workflow.run_investigation(req, incident_data=inc_d)

    assert result.is_sufficient is False
    assert result.hypotheses[0].code == "H6"
    assert result.conflict_lifecycle == ConflictLifecycle.CONFLICT_UNRESOLVED
    assert "INSUFFICIENT" in result.diagnosis_title.upper()

    transitions = result.conflict_transitions
    assert len(transitions) == 3
    assert transitions[-1].to_state == ConflictLifecycle.CONFLICT_UNRESOLVED
    assert transitions[-1].rule_id == "RULE-CONFLICT-UNRESOLVED"


def test_forbidden_anti_patterns_are_absent():
    """CI gate: Grep domain/ and services/ for forbidden substring checks and hardcoded incident IDs."""
    base_dir = Path(__file__).resolve().parent.parent.parent
    check_dirs = [base_dir / "domain", base_dir / "services"]

    forbidden_patterns = [
        re.compile(r'"RULE-MAP-003"\s+in\s+ev\.evidence_id'),
        re.compile(r'"TRUNCATED"\s+in\s+ev\.evidence_id'),
        re.compile(r'"C01"'),
    ]

    violations = []
    for directory in check_dirs:
        for py_file in directory.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            for line_no, line in enumerate(text.splitlines(), start=1):
                for pat in forbidden_patterns:
                    if pat.search(line):
                        violations.append(f"{py_file.name}:{line_no} matches {pat.pattern}: {line.strip()}")

    # Ensure graph.py does not contain hardcoded "INC-2026-002"
    graph_py = base_dir / "services" / "agent" / "graph.py"
    graph_text = graph_py.read_text(encoding="utf-8")
    for line_no, line in enumerate(graph_text.splitlines(), start=1):
        if "INC-2026-002" in line and not line.strip().startswith("#"):
            violations.append(f"graph.py:{line_no} contains hardcoded INC-2026-002: {line.strip()}")

    assert not violations, f"Found forbidden anti-patterns:\n" + "\n".join(violations)
