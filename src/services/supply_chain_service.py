"""
SupplyChainService — chain mapping, risk scoring, concentration analysis.
"""
from __future__ import annotations
import logging
import math
from typing import Dict, List, Optional, Tuple

from src.models.supply_chain_node import SupplyChainNode, NodeType

logger = logging.getLogger(__name__)


class SupplyChainService:
    """Supply chain graph analysis and risk scoring."""

    def __init__(self) -> None:
        self._nodes: Dict[str, SupplyChainNode] = {}

    def add_node(self, node: SupplyChainNode) -> None:
        self._nodes[node.node_id] = node

    def add_edge(self, from_id: str, to_id: str) -> None:
        if from_id in self._nodes:
            self._nodes[from_id].add_connection(to_id)

    def get_node(self, node_id: str) -> Optional[SupplyChainNode]:
        return self._nodes.get(node_id)

    def get_nodes_by_type(self, node_type: NodeType) -> List[SupplyChainNode]:
        return [n for n in self._nodes.values() if n.node_type == node_type]

    def get_nodes_by_country(self, country: str) -> List[SupplyChainNode]:
        return [n for n in self._nodes.values() if n.country == country]

    def build_chain(self, commodity: str) -> List[List[str]]:
        """Build supply chain paths from origin to end market."""
        origins = [n.node_id for n in self.get_nodes_by_type(NodeType.ORIGIN_COUNTRY)]
        end_markets = [n.node_id for n in self.get_nodes_by_type(NodeType.END_MARKET)]

        paths = []
        for origin in origins:
            node = self._nodes.get(origin)
            if not node or commodity not in node.commodities:
                continue
            path = self._bfs_path(origin, end_markets)
            if path:
                paths.append(path)
        return paths

    def _bfs_path(self, start: str, targets: List[str]) -> Optional[List[str]]:
        """BFS to find path from start to any target."""
        from collections import deque
        visited = {start}
        queue = deque([(start, [start])])
        while queue:
            current, path = queue.popleft()
            if current in targets:
                return path
            node = self._nodes.get(current)
            if node:
                for neighbor in node.connected_to:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, path + [neighbor]))
        return None

    @staticmethod
    def compute_hhi(country_shares: Dict[str, float]) -> float:
        """Compute Herfindahl-Hirschman Index for concentration."""
        total = sum(country_shares.values())
        if total <= 0:
            return 0.0
        shares_normalized = {c: s / total for c, s in country_shares.items()}
        return sum(s ** 2 for s in shares_normalized.values()) * 10000

    @staticmethod
    def interpret_hhi(hhi: float) -> str:
        if hhi < 1500:
            return "Unconcentrated"
        elif hhi < 2500:
            return "Moderately Concentrated"
        return "Highly Concentrated"

    def compute_node_risk(self, node_id: str) -> float:
        """Compute risk score for a single node (0-100)."""
        node = self._nodes.get(node_id)
        if not node:
            return 0.0

        score = 30.0  # Base risk
        # High concentration = high risk
        if node.capacity_share > 50:
            score += 30
        elif node.capacity_share > 25:
            score += 15
        # Many connections = hub = higher systemic risk
        score += min(len(node.connected_to) * 3, 20)
        # Geographic risk heuristic
        high_risk_countries = {"Russia", "DR Congo", "Myanmar", "Iran", "Venezuela"}
        if node.country in high_risk_countries:
            score += 20
        return min(100, score)

    def detect_bottlenecks(self) -> List[Dict]:
        """Detect supply chain bottlenecks (single points of failure)."""
        bottlenecks = []
        for node in self._nodes.values():
            # A bottleneck has high capacity share OR is sole connection between stages
            if node.capacity_share > 40:
                bottlenecks.append({
                    "node_id": node.node_id, "name": node.name, "country": node.country,
                    "capacity_share": node.capacity_share, "type": "Concentration",
                    "risk_score": self.compute_node_risk(node.node_id),
                })
            # Check if removing this node disconnects the graph
            downstream = self._nodes.get(node.connected_to[0]) if node.connected_to else None
            if downstream and len(node.connected_to) == 1:
                inbound = sum(1 for n in self._nodes.values() if node.node_id in n.connected_to)
                if inbound > 2:
                    bottlenecks.append({
                        "node_id": node.node_id, "name": node.name, "country": node.country,
                        "capacity_share": node.capacity_share, "type": "Chokepoint",
                        "risk_score": self.compute_node_risk(node.node_id),
                    })
        return sorted(bottlenecks, key=lambda b: b["risk_score"], reverse=True)
