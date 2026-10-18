"""Unit tests for DirectedGraph data structure and Substation Graph Traversal."""
import pytest
from services.graph.directed_graph import DirectedGraph
from services.graph.repository import InMemoryGraphRepository


def test_directed_graph_construction_and_traversal():
    graph = DirectedGraph()

    # Add nodes
    graph.add_node("BUS_A", "BUS", voltage=33.0)
    graph.add_node("T1", "TRANSFORMER", rating=25.0)
    graph.add_node("BUS_B", "BUS", voltage=11.0)
    graph.add_node("F12", "FEEDER", name="Feeder 12")
    graph.add_node("CB12", "BREAKER", rating=2000.0)

    # Add directed edges
    graph.add_edge("BUS_A", "T1", "FEEDS")
    graph.add_edge("T1", "BUS_B", "FEEDS")
    graph.add_edge("BUS_B", "F12", "FEEDS")
    graph.add_edge("F12", "CB12", "INTERRUPTED_BY")

    assert graph.total_nodes == 5
    assert graph.total_edges == 4

    # Test shortest path BFS traversal
    path = graph.shortest_path("BUS_A", "CB12")
    assert path == ["BUS_A", "T1", "BUS_B", "F12", "CB12"]

    # Test predecessor & successor queries
    successors = graph.get_successors("BUS_B", "FEEDS")
    assert len(successors) == 1
    assert successors[0].node_id == "F12"

    predecessors = graph.get_predecessors("T1", "FEEDS")
    assert len(predecessors) == 1
    assert predecessors[0].node_id == "BUS_A"

    # Test ancestor traversal by type
    transformers = graph.find_ancestors_of_type("CB12", "TRANSFORMER")
    assert len(transformers) == 1
    assert transformers[0].node_id == "T1"


@pytest.mark.asyncio
async def test_substation_protection_chain_via_graph_traversal():
    repo = InMemoryGraphRepository()

    # Trace feeder F12 protection chain dynamically through the graph
    chain_f12 = await repo.get_feeder_protection_chain("F12")
    assert chain_f12.is_topology_complete is True
    assert chain_f12.primary_relay_id == "RELAY_12"
    assert chain_f12.controlled_breaker_id == "CB12"
    assert chain_f12.connected_bus_id == "BUS_B"
    assert chain_f12.upstream_transformer_id == "T1"
    assert "Industrial Park Substation" in chain_f12.downstream_equipment
    assert chain_f12.metadata["backend"] == "in-memory DirectedGraph"
    assert chain_f12.metadata["total_graph_nodes"] > 10

    # Test sensor bindings via graph edges
    bindings = await repo.get_sensor_bindings("IED_12")
    assert len(bindings) >= 4
    sensor_ids = {b["sensor_id"] for b in bindings}
    assert {"CT12A", "CT12B", "CT12C", "VT12"} <= sensor_ids

    # Test equipment relationships
    rel = await repo.get_equipment_relationships("RELAY_12")
    assert rel["entity_id"] == "RELAY_12"
    out_targets = {e["target"] for e in rel["relationships"]["outgoing"]}
    assert "F12" in out_targets
    assert "CB12" in out_targets
