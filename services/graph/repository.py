import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from domain.models.equipment import Substation, Feeder, Breaker, Relay, IED, Sensor, Bus, Transformer
from domain.models.results import TopologyQueryResult
from services.graph.directed_graph import DirectedGraph, GraphNode, GraphEdge
from services.config import SUBSTATION_FILE


class GraphRepository(ABC):
    """Abstract interface for querying engineering topology and equipment relationships."""

    @abstractmethod
    async def get_feeder_protection_chain(self, feeder_id: str) -> TopologyQueryResult:
        pass

    @abstractmethod
    async def get_equipment_relationships(self, equipment_id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def get_sensor_bindings(self, ied_id: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def get_substation_topology(self, substation_id: str = "OGS-01") -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_declared_channel_mapping(self, ied_id: str) -> Optional[Dict[str, str]]:
        pass

    @abstractmethod
    def get_commissioned_channel_mapping(self, ied_id: str) -> Dict[str, str]:
        pass


class InMemoryGraphRepository(GraphRepository):
    """Substation graph repository powered by the seeded DirectedGraph topology engine.

    Implements mathematical graph traversal (BFS, predecessor/successor queries,
    and hierarchical path traversal) for protection chain determination.
    """

    def __init__(self, seed_file: Optional[Union[str, Path]] = None):
        target_path = Path(seed_file) if seed_file else SUBSTATION_FILE
        if not os.path.exists(target_path):
            raise FileNotFoundError(f"Required substation topology seed file not found: {target_path}")

        with open(target_path, "r", encoding="utf-8") as f:
            self._seed_data: Dict[str, Any] = json.load(f)

        # Build the seeded DirectedGraph model
        self.graph: DirectedGraph = DirectedGraph()
        self._populate_graph_from_seed()

    def _populate_graph_from_seed(self):
        """Constructs mathematical directed graph topology with nodes and relationship edges."""
        sub = self._seed_data.get("substation", {"id": "OGS-01", "name": "Orion Grid Substation OGS-01"})
        self.graph.add_node(sub["id"], "SUBSTATION", **sub)

        for b in self._seed_data.get("buses", []):
            self.graph.add_node(b["bus_id"], "BUS", **b)
            self.graph.add_edge(sub["id"], b["bus_id"], "CONTAINS")

        for t in self._seed_data.get("transformers", []):
            self.graph.add_node(t["transformer_id"], "TRANSFORMER", **t)
            prim = t.get("primary_bus", "BUS_A")
            sec = t.get("secondary_bus", "BUS_B")
            self.graph.add_edge(prim, t["transformer_id"], "FEEDS")
            self.graph.add_edge(t["transformer_id"], sec, "FEEDS")

        feeders = self._seed_data.get("feeders", [])
        feeders_list = feeders if isinstance(feeders, list) else list(feeders.values())
        for f in feeders_list:
            f_id = f["feeder_id"]
            self.graph.add_node(f_id, "FEEDER", **f)
            self.graph.add_edge(f["connected_bus_id"], f_id, "FEEDS")
            for down in f.get("downstream_equipment", []):
                self.graph.add_node(down, "LOAD", name=down)
                self.graph.add_edge(f_id, down, "DELIVERS_TO")

        breakers = self._seed_data.get("breakers", [])
        breakers_list = breakers if isinstance(breakers, list) else list(breakers.values())
        for brk in breakers_list:
            self.graph.add_node(brk["breaker_id"], "BREAKER", **brk)

        relays = self._seed_data.get("relays", [])
        relays_list = relays if isinstance(relays, list) else list(relays.values())
        for rel in relays_list:
            rel_id = rel["relay_id"]
            self.graph.add_node(rel_id, "RELAY", **rel)
            f_id = rel["protected_feeder_id"]
            brk_id = rel["controlled_breaker_id"]
            self.graph.add_edge(rel_id, f_id, "PROTECTS")
            self.graph.add_edge(rel_id, brk_id, "CONTROLS")
            self.graph.add_edge(f_id, brk_id, "INTERRUPTED_BY")

        ieds = self._seed_data.get("ieds", [])
        ieds_list = ieds if isinstance(ieds, list) else list(ieds.values())
        for ied in ieds_list:
            self.graph.add_node(ied["ied_id"], "IED", **ied)

        sensors = self._seed_data.get("sensors", [])
        sensors_list = sensors if isinstance(sensors, list) else list(sensors.values())
        for s in sensors_list:
            self.graph.add_node(s["sensor_id"], "SENSOR", **s)

        # Connect sensors to IEDs via mapping
        for ied in ieds_list:
            ied_id = ied["ied_id"]
            for ch, s_id in ied.get("ct_channel_mapping", {}).items():
                if self.graph.has_node(s_id):
                    self.graph.add_edge(s_id, ied_id, "MEASURES", channel=ch, type="CT")
            for ch, s_id in ied.get("vt_channel_mapping", {}).items():
                if self.graph.has_node(s_id):
                    self.graph.add_edge(s_id, ied_id, "MEASURES", channel=ch, type="VT")

    def get_declared_channel_mapping(self, ied_id: str) -> Optional[Dict[str, str]]:
        clean_ied = ied_id.upper().strip()
        ied_node = self.graph.get_node(clean_ied)
        if ied_node and "declared_channel_phase_map" in ied_node.attributes:
            return ied_node.attributes["declared_channel_phase_map"]
        return None

    def get_commissioned_channel_mapping(self, ied_id: str) -> Dict[str, str]:
        clean_ied = ied_id.upper().strip()
        ied_node = self.graph.get_node(clean_ied)
        if ied_node and "ct_channel_mapping" in ied_node.attributes:
            return ied_node.attributes["ct_channel_mapping"]
        return {}

    async def get_feeder_protection_chain(self, feeder_id: str) -> TopologyQueryResult:
        clean_id = feeder_id.upper().strip()
        node = self.graph.get_node(clean_id)

        # If not direct match, search by substring or bay
        if not node or node.node_type != "FEEDER":
            for n_id, n in self.graph._nodes.items():
                if n.node_type == "FEEDER" and (clean_id in n_id or clean_id in n.attributes.get("bay_id", "")):
                    clean_id = n_id
                    node = n
                    break

        if not node:
            return TopologyQueryResult(
                feeder_id=feeder_id,
                bay_id="UNKNOWN_BAY",
                connected_bus_id="UNKNOWN_BUS",
                primary_relay_id="UNKNOWN_RELAY",
                controlled_breaker_id="UNKNOWN_BREAKER",
                ied_id="UNKNOWN_IED",
                is_topology_complete=False,
                metadata={"error": f"Feeder {feeder_id} not found in Substation OGS-01 directed graph."},
            )

        f_attrs = node.attributes

        # Use graph traversals to extract topology facts
        # 1. Connected Bus: predecessor connected by 'FEEDS'
        bus_predecessors = self.graph.get_predecessors(clean_id, relation="FEEDS")
        connected_bus_id = bus_predecessors[0].node_id if bus_predecessors else f_attrs.get("connected_bus_id", "UNKNOWN_BUS")

        # 2. Upstream Transformer: ancestor of type TRANSFORMER
        ancestor_transformers = self.graph.find_ancestors_of_type(clean_id, target_type="TRANSFORMER")
        upstream_xfmr_id = ancestor_transformers[0].node_id if ancestor_transformers else f_attrs.get("upstream_transformer_id")

        # 3. Controlled Breaker: successor connected by 'INTERRUPTED_BY'
        breaker_successors = self.graph.get_successors(clean_id, relation="INTERRUPTED_BY")
        breaker_id = breaker_successors[0].node_id if breaker_successors else f_attrs.get("controlled_breaker_id", "UNKNOWN_BREAKER")

        # 4. Primary Relay: predecessor connected by 'PROTECTS'
        relay_predecessors = self.graph.get_predecessors(clean_id, relation="PROTECTS")
        primary_relay_id = relay_predecessors[0].node_id if relay_predecessors else f_attrs.get("primary_relay_id", "UNKNOWN_RELAY")

        # 5. Downstream Loads: successors connected by 'DELIVERS_TO'
        downstream_nodes = self.graph.get_successors(clean_id, relation="DELIVERS_TO")
        downstream_loads = [n.node_id for n in downstream_nodes] if downstream_nodes else f_attrs.get("downstream_equipment", [])

        # 6. Sensor IDs and IED ID
        ied_id = f_attrs.get("ied_id", "UNKNOWN_IED")
        sensor_ids = f_attrs.get("sensor_ids", [])

        return TopologyQueryResult(
            feeder_id=clean_id,
            bay_id=f_attrs.get("bay_id", f"BAY_{clean_id}"),
            connected_bus_id=connected_bus_id,
            primary_relay_id=primary_relay_id,
            controlled_breaker_id=breaker_id,
            ied_id=ied_id,
            sensor_ids=sensor_ids,
            upstream_transformer_id=upstream_xfmr_id,
            downstream_equipment=downstream_loads,
            is_topology_complete=True,
            metadata={
                "source": "DirectedGraph topological traversal",
                "backend": "in-memory DirectedGraph",
                "total_graph_nodes": self.graph.total_nodes,
                "total_graph_edges": self.graph.total_edges,
            },
        )

    async def get_equipment_relationships(self, equipment_id: str) -> Dict[str, Any]:
        eq_upper = equipment_id.upper().strip()
        node = self.graph.get_node(eq_upper)
        if not node:
            return {"error": f"Equipment {equipment_id} not found in graph topology"}

        out_edges = self.graph.get_out_edges(eq_upper)
        in_edges = self.graph.get_in_edges(eq_upper)

        return {
            "entity_id": node.node_id,
            "entity_type": node.node_type.lower(),
            "details": node.attributes,
            "relationships": {
                "outgoing": [{"target": e.target_id, "relation": e.relation, **e.attributes} for e in out_edges],
                "incoming": [{"source": e.source_id, "relation": e.relation, **e.attributes} for e in in_edges],
            }
        }

    async def get_sensor_bindings(self, ied_id: str) -> List[Dict[str, Any]]:
        clean_ied = ied_id.upper().strip()
        in_edges = self.graph.get_in_edges(clean_ied, relation="MEASURES")
        bindings = []
        for edge in in_edges:
            sensor_node = self.graph.get_node(edge.source_id)
            s_attrs = sensor_node.attributes if sensor_node else {}
            bindings.append({
                "channel": edge.attributes.get("channel", ""),
                "sensor_id": edge.source_id,
                "type": edge.attributes.get("type", "CT"),
                **s_attrs,
            })
        return bindings

    async def get_substation_topology(self, substation_id: str = "OGS-01") -> Dict[str, Any]:
        return self._seed_data
