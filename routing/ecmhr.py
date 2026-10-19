from dataclasses import dataclass
import math
from typing import Dict, List, Optional, Set, Tuple, Union

import networkx as nx

from core.sensor import SensorNode
from core.sink import SinkNode


NodeId = Union[int, str]


@dataclass
class ECMHRRouteResult:
    path: List[NodeId]
    hop_count: int
    total_distance_m: float
    bottleneck_energy_j: float

    def __repr__(self) -> str:
        path_text = " -> ".join(str(n) for n in self.path)
        return (
            f"ECMHRRouteResult("
            f"path={path_text}, "
            f"hops={self.hop_count}, "
            f"distance={self.total_distance_m:.2f}m, "
            f"bottleneck={self.bottleneck_energy_j:.4f}J)"
        )


@dataclass
class _PathLabel:
    path: List[NodeId]
    hop_count: int
    total_distance_m: float
    bottleneck_energy_j: float


class ECMHRRouter:
    """
    Energy-Constrained Minimum-Hop Routing (ECMHR).

    Logic cốt lõi:
    1. Các relay trung gian bắt buộc phải có mức pin trên ngưỡng:
       remaining_energy > initial_energy * energy_threshold_ratio
    2. LOW_ENERGY source vẫn được phép gửi gói tin của chính nó
       (nhưng không được làm relay cho node khác).
    3. Tiêu chí chọn đường:
       Min Hop Count -> Max Bottleneck Residual Energy -> Min Physical Distance.
    """

    def __init__(
        self,
        network,
        energy_threshold_ratio: float = 0.15
    ):
        self.network = network
        self.graph = network.graph
        self.sink = network.sink
        self.sink_id = network.sink.node_id
        self.energy_threshold_ratio = float(energy_threshold_ratio)

        self.sensor_map: Dict[int, SensorNode] = {
            sensor.node_id: sensor
            for sensor in network.sensors
        }

    def _node_xy(self, node_id: NodeId) -> Tuple[float, float]:
        if node_id == self.sink_id:
            return (self.sink.x, self.sink.y)
        sensor = self.sensor_map[node_id]
        return (sensor.x, sensor.y)

    def _distance(self, u: NodeId, v: NodeId) -> float:
        edge = self.graph.get_edge_data(u, v)
        if edge and "distance" in edge:
            return float(edge["distance"])
        ux, uy = self._node_xy(u)
        vx, vy = self._node_xy(v)
        return math.hypot(ux - vx, uy - vy)

    def _is_energy_eligible_relay(self, node_id: NodeId) -> bool:
        if node_id == self.sink_id:
            return True
        sensor = self.sensor_map.get(node_id)
        if sensor is None or not sensor.is_alive():
            return False
        return sensor.energy_ratio() > self.energy_threshold_ratio

    def _build_relay_labels(self) -> Dict[NodeId, _PathLabel]:
        """
        Duyệt ngược từ Sink qua các relay đủ năng lượng để tính nhãn đường đi
        tối ưu (ít hop nhất, bottleneck lớn nhất, khoảng cách nhỏ nhất) đến Sink.
        """
        if self.sink_id not in self.graph:
            return {}

        # Tập relay hợp lệ
        eligible_relays: Set[NodeId] = {
            sensor.node_id
            for sensor in self.network.sensors
            if self._is_energy_eligible_relay(sensor.node_id)
        }

        # Subgraph chỉ gồm relay đủ pin + Sink
        valid_nodes = eligible_relays | {self.sink_id}
        adj: Dict[NodeId, List[NodeId]] = {
            n: [nbr for nbr in self.graph.neighbors(n) if nbr in valid_nodes]
            for n in valid_nodes
            if n in self.graph
        }

        if self.sink_id not in adj:
            return {}

        # BFS tính hop distance từ Sink
        distances: Dict[NodeId, int] = {self.sink_id: 0}
        queue: List[NodeId] = [self.sink_id]
        levels: Dict[int, List[NodeId]] = {0: [self.sink_id]}

        while queue:
            curr = queue.pop(0)
            d = distances[curr]
            for nbr in adj.get(curr, []):
                if nbr not in distances:
                    distances[nbr] = d + 1
                    levels.setdefault(d + 1, []).append(nbr)
                    queue.append(nbr)

        labels: Dict[NodeId, _PathLabel] = {
            self.sink_id: _PathLabel(
                path=[self.sink_id],
                hop_count=0,
                total_distance_m=0.0,
                bottleneck_energy_j=float("inf")
            )
        }

        # Xây dựng đường đi tối ưu theo từng mức hop tăng dần
        max_dist = max(levels.keys()) if levels else 0
        for d in range(1, max_dist + 1):
            for u in levels.get(d, []):
                sensor_u = self.sensor_map[u]
                u_energy = sensor_u.remaining_energy

                candidates = []
                for nbr in adj.get(u, []):
                    if distances.get(nbr) == d - 1 and nbr in labels:
                        next_label = labels[nbr]
                        tot_dist = (
                            self._distance(u, nbr)
                            + next_label.total_distance_m
                        )
                        bottleneck = min(
                            u_energy,
                            next_label.bottleneck_energy_j
                        )
                        score = (
                            1 + next_label.hop_count,
                            -bottleneck,
                            tot_dist
                        )
                        label = _PathLabel(
                            path=[u] + next_label.path,
                            hop_count=1 + next_label.hop_count,
                            total_distance_m=tot_dist,
                            bottleneck_energy_j=bottleneck
                        )
                        candidates.append((score, label))

                if candidates:
                    candidates.sort(key=lambda item: item[0])
                    labels[u] = candidates[0][1]

        return labels

    def route_source(
        self,
        source_id: int,
        labels: Optional[Dict[NodeId, _PathLabel]] = None
    ) -> Optional[ECMHRRouteResult]:
        """
        Tìm đường đi cho một source cụ thể.
        Source có thể là LOW_ENERGY nhưng vẫn được gửi gói tin của chính nó.
        """
        source = self.sensor_map.get(source_id)
        if source is None or not source.is_alive():
            return None

        # 1. Kết nối trực tiếp với Sink (1 hop)
        if (
            self.sink_id in self.graph
            and self.graph.has_edge(source_id, self.sink_id)
        ):
            dist = self._distance(source_id, self.sink_id)
            return ECMHRRouteResult(
                path=[source_id, self.sink_id],
                hop_count=1,
                total_distance_m=dist,
                bottleneck_energy_j=source.remaining_energy
            )

        if labels is None:
            labels = self._build_relay_labels()

        if not labels:
            return None

        # 2. Tìm hàng xóm là relay hợp lệ có đường đến Sink
        candidates = []
        for nbr in self.graph.neighbors(source_id):
            if nbr in labels:
                next_label = labels[nbr]
                hop_count = 1 + next_label.hop_count
                tot_dist = (
                    self._distance(source_id, nbr)
                    + next_label.total_distance_m
                )
                bottleneck = next_label.bottleneck_energy_j
                if math.isinf(bottleneck):
                    bottleneck = source.remaining_energy

                score = (
                    hop_count,
                    -bottleneck,
                    tot_dist
                )
                result = ECMHRRouteResult(
                    path=[source_id] + next_label.path,
                    hop_count=hop_count,
                    total_distance_m=tot_dist,
                    bottleneck_energy_j=bottleneck
                )
                candidates.append((score, result))

        if not candidates:
            return None

        # Lọc các ứng viên ít hop nhất, sau đó chọn max bottleneck -> min dist
        min_hops = min(item[0][0] for item in candidates)
        best_candidates = [
            item for item in candidates
            if item[0][0] == min_hops
        ]
        best_candidates.sort(key=lambda item: item[0])
        return best_candidates[0][1]

    def build_route_table(self) -> Dict[int, Optional[ECMHRRouteResult]]:
        """
        Xây dựng bảng định tuyến cho toàn bộ cảm biến trong mạng.
        """
        labels = self._build_relay_labels()
        route_table: Dict[int, Optional[ECMHRRouteResult]] = {}

        for sensor in self.network.sensors:
            sid = sensor.node_id
            if not sensor.is_alive():
                route_table[sid] = None
                continue
            route_table[sid] = self.route_source(sid, labels=labels)

        return route_table


def find_ecmhr_route(
    network,
    source_id: int,
    energy_threshold_ratio: float = 0.15
) -> Optional[ECMHRRouteResult]:
    """
    Hàm tiện ích tìm route ECMHR cho một node.
    """
    router = ECMHRRouter(
        network=network,
        energy_threshold_ratio=energy_threshold_ratio
    )
    return router.route_source(source_id)
