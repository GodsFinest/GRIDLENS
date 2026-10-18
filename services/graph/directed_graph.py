"""Mathematical Directed Graph data structure for power-system equipment topology.

Provides typed nodes, directional relationship edges, and graph traversal
algorithms (breadth-first search, path-finding, predecessor and successor tracking)
for tracing substation protection chains and electrical equipment hierarchies.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, Tuple
from collections import deque


@dataclass
class GraphNode:
    """Represents an equipment entity within the substation graph."""
    node_id: str
    node_type: str  # e.g., "SUBSTATION", "BUS", "TRANSFORMER", "FEEDER", "BREAKER", "RELAY", "IED", "SENSOR"
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """Represents a directional relationship between two equipment entities."""
    source_id: str
    target_id: str
    relation: str  # e.g., "FEEDS", "CONTROLS", "PROTECTED_BY", "MEASURES", "ASSOCIATED_WITH"
    attributes: Dict[str, Any] = field(default_factory=dict)


class DirectedGraph:
    """In-memory directed graph with adjacency lists and traversal algorithms."""

    def __init__(self):
        self._nodes: Dict[str, GraphNode] = {}
        # Outgoing adjacency: source_id -> list of GraphEdge
        self._out_edges: Dict[str, List[GraphEdge]] = {}
        # Incoming adjacency: target_id -> list of GraphEdge
        self._in_edges: Dict[str, List[GraphEdge]] = {}

    def add_node(self, node_id: str, node_type: str, **attributes) -> GraphNode:
        """Adds a node to the graph or updates existing node attributes."""
        node = GraphNode(node_id=node_id, node_type=node_type, attributes=attributes)
        self._nodes[node_id] = node
        if node_id not in self._out_edges:
            self._out_edges[node_id] = []
        if node_id not in self._in_edges:
            self._in_edges[node_id] = []
        return node

    def add_edge(self, source_id: str, target_id: str, relation: str, **attributes) -> GraphEdge:
        """Adds a directed edge between two existing nodes."""
        if source_id not in self._nodes:
            raise KeyError(f"Source node '{source_id}' does not exist in graph.")
        if target_id not in self._nodes:
            raise KeyError(f"Target node '{target_id}' does not exist in graph.")

        edge = GraphEdge(source_id=source_id, target_id=target_id, relation=relation, attributes=attributes)
        self._out_edges[source_id].append(edge)
        self._in_edges[target_id].append(edge)
        return edge

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        return self._nodes.get(node_id)

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def get_out_edges(self, node_id: str, relation: Optional[str] = None) -> List[GraphEdge]:
        edges = self._out_edges.get(node_id, [])
        if relation:
            return [e for e in edges if e.relation == relation]
        return edges

    def get_in_edges(self, node_id: str, relation: Optional[str] = None) -> List[GraphEdge]:
        edges = self._in_edges.get(node_id, [])
        if relation:
            return [e for e in edges if e.relation == relation]
        return edges

    def get_successors(self, node_id: str, relation: Optional[str] = None) -> List[GraphNode]:
        """Returns direct child/downstream nodes."""
        edges = self.get_out_edges(node_id, relation)
        return [self._nodes[e.target_id] for e in edges if e.target_id in self._nodes]

    def get_predecessors(self, node_id: str, relation: Optional[str] = None) -> List[GraphNode]:
        """Returns direct parent/upstream nodes."""
        edges = self.get_in_edges(node_id, relation)
        return [self._nodes[e.source_id] for e in edges if e.source_id in self._nodes]

    def shortest_path(self, start_id: str, target_id: str) -> Optional[List[str]]:
        """Finds the shortest directed path between two nodes using Breadth-First Search (BFS)."""
        if start_id not in self._nodes or target_id not in self._nodes:
            return None
        if start_id == target_id:
            return [start_id]

        queue: deque = deque([[start_id]])
        visited: Set[str] = {start_id}

        while queue:
            path = queue.popleft()
            curr = path[-1]

            if curr == target_id:
                return path

            for edge in self._out_edges.get(curr, []):
                neighbor = edge.target_id
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])
        return None

    def find_ancestors_of_type(self, node_id: str, target_type: str) -> List[GraphNode]:
        """Traverses upstream via incoming edges to find all ancestor nodes of a given type."""
        ancestors: List[GraphNode] = []
        visited: Set[str] = {node_id}
        queue: deque = deque([node_id])

        while queue:
            curr = queue.popleft()
            for edge in self._in_edges.get(curr, []):
                src = edge.source_id
                if src not in visited:
                    visited.add(src)
                    if self._nodes[src].node_type == target_type:
                        ancestors.append(self._nodes[src])
                    queue.append(src)
        return ancestors

    def find_descendants_of_type(self, node_id: str, target_type: str) -> List[GraphNode]:
        """Traverses downstream via outgoing edges to find all descendant nodes of a given type."""
        descendants: List[GraphNode] = []
        visited: Set[str] = {node_id}
        queue: deque = deque([node_id])

        while queue:
            curr = queue.popleft()
            for edge in self._out_edges.get(curr, []):
                tgt = edge.target_id
                if tgt not in visited:
                    visited.add(tgt)
                    if self._nodes[tgt].node_type == target_type:
                        descendants.append(self._nodes[tgt])
                    queue.append(tgt)
        return descendants

    @property
    def total_nodes(self) -> int:
        return len(self._nodes)

    @property
    def total_edges(self) -> int:
        return sum(len(edges) for edges in self._out_edges.values())
