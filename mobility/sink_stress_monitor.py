from collections import deque
from dataclasses import dataclass
import math
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx


@dataclass
class SinkStressSnapshot:
    round_number: int
    near_sink_nodes_count: int
    stressed_relays_count: int
    overloaded_ratio: float
    drain_ratio: float
    max_route_concentration: float
    alert_load: bool
    alert_drain: bool
    alert_concentration: bool
    active_alerts_count: int
    should_alert: bool

    @property
    def stress_alert(self) -> bool:
        return self.should_alert


class SinkStressMonitor:
    """
    Theo dõi áp lực lưu lượng và năng lượng quanh Sink dựa trên 3 tín hiệu sớm:
    1. Recent Forwarding Load (L_i): tải chuyển tiếp trong cửa sổ W rounds (24h).
    2. Energy Drain Rate (D_i): tốc độ tiêu hao pin trung bình trong cửa sổ 24h.
    3. Route Concentration (C_i): tỷ lệ route của mạng hội tụ qua một relay.
    """

    def __init__(
        self,
        network,
        load_window_rounds: int = 24,
        overload_factor: float = 1.8,
        overloaded_ratio_threshold: float = 0.30,
        drain_ratio_threshold: float = 1.50,
        route_concentration_threshold: float = 0.30,
        monitor_hops: int = 2
    ):
        self.network = network
        self.load_window_rounds = int(load_window_rounds)
        self.overload_factor = float(overload_factor)
        self.overloaded_ratio_threshold = float(overloaded_ratio_threshold)
        self.drain_ratio_threshold = float(drain_ratio_threshold)
        self.route_concentration_threshold = float(route_concentration_threshold)
        self.monitor_hops = int(monitor_hops)

        # Lịch sử lưu lượng chuyển tiếp mỗi round: node_id -> deque of int
        self.forwarded_history: Dict[int, deque] = {
            sensor.node_id: deque(maxlen=self.load_window_rounds)
            for sensor in network.sensors
        }

        # Lịch sử năng lượng mỗi round: node_id -> deque of float
        self.energy_history: Dict[int, deque] = {
            sensor.node_id: deque(maxlen=self.load_window_rounds + 1)
            for sensor in network.sensors
        }

        self.last_snapshot: Optional[SinkStressSnapshot] = None

    def record_round(self, current_round: int) -> None:
        """
        Ghi nhận số packet chuyển tiếp và mức pin của từng node ở cuối mỗi round.
        """
        for sensor in self.network.sensors:
            sid = sensor.node_id
            # Sensor.forwarded_packets_in_round (nếu có) hoặc delta từ total
            # SensorNode có packets_forwarded (tổng lũy kế)
            current_fwd = getattr(sensor, "forwarded_packets", 0)
            prev_total_fwd = getattr(sensor, "_prev_total_fwd_recorded", 0)
            delta_fwd = max(0, current_fwd - prev_total_fwd)
            sensor._prev_total_fwd_recorded = current_fwd

            if sid not in self.forwarded_history:
                self.forwarded_history[sid] = deque(maxlen=self.load_window_rounds)
            self.forwarded_history[sid].append(delta_fwd)

            if sid not in self.energy_history:
                self.energy_history[sid] = deque(maxlen=self.load_window_rounds + 1)
            self.energy_history[sid].append(sensor.remaining_energy)

    def get_node_forwarded_in_window(self, node_id: int) -> int:
        """
        Lấy tổng số packet chuyển tiếp của một sensor trong cửa sổ quan sát W rounds gần nhất.
        """
        hist = self.forwarded_history.get(node_id)
        return sum(hist) if hist else 0

    def get_near_sink_relays(self) -> List[int]:
        """
        Lấy danh sách các sensor nằm trong vòng monitor_hops (1 hop hoặc 2 hop)
        tính từ vị trí Sink hiện tại trên đồ thị mạng.
        """
        sink_id = self.network.sink.node_id
        if sink_id not in self.network.graph:
            return []

        # BFS từ Sink đến khoảng cách hop <= monitor_hops
        near_nodes = []
        try:
            lengths = nx.single_source_shortest_path_length(
                self.network.graph,
                sink_id,
                cutoff=self.monitor_hops
            )
            for node_id, dist in lengths.items():
                if node_id != sink_id and dist >= 1:
                    near_nodes.append(node_id)
        except Exception:
            near_nodes = []

        return near_nodes

    def compute_route_concentration(
        self,
        route_table: Dict[int, object]
    ) -> Dict[int, float]:
        """
        Tính Route Concentration C_i cho từng relay từ bảng route hiện tại:
        C_i = (số route có node i làm relay trung gian) / (tổng số route hợp lệ)
        """
        relay_counts: Dict[int, int] = {}
        valid_routes_count = 0

        for source_id, route in route_table.items():
            if route is None:
                continue
            path = getattr(route, "path", None)
            if not path or len(path) < 2:
                continue

            valid_routes_count += 1
            # Relay là các node trung gian: path[1:-1]
            for relay_id in path[1:-1]:
                if isinstance(relay_id, int):
                    relay_counts[relay_id] = relay_counts.get(relay_id, 0) + 1

        if valid_routes_count == 0:
            return {}

        return {
            node_id: count / valid_routes_count
            for node_id, count in relay_counts.items()
        }

    def evaluate(
        self,
        current_round: int,
        route_table: Dict[int, object]
    ) -> SinkStressSnapshot:
        """
        Đánh giá 3 tín hiệu cảnh báo tại vòng lặp hiện tại.
        Trả về SinkStressSnapshot chi tiết.
        """
        near_sink_nodes = self.get_near_sink_relays()
        if not near_sink_nodes:
            snapshot = SinkStressSnapshot(
                round_number=current_round,
                near_sink_nodes_count=0,
                stressed_relays_count=0,
                overloaded_ratio=0.0,
                drain_ratio=1.0,
                max_route_concentration=0.0,
                alert_load=False,
                alert_drain=False,
                alert_concentration=False,
                active_alerts_count=0,
                should_alert=False
            )
            self.last_snapshot = snapshot
            return snapshot

        # ---------------------------------------------------------
        # TÍN HIỆU 1: Recent Forwarding Load (L_i)
        # ---------------------------------------------------------
        recent_fwd_map: Dict[int, int] = {}
        for sid, hist in self.forwarded_history.items():
            recent_fwd_map[sid] = sum(hist)

        # Tính trung bình trên các relay đang hoạt động (> 0 packets)
        active_fwd_values = [v for v in recent_fwd_map.values() if v > 0]
        mean_fwd = (
            sum(active_fwd_values) / len(active_fwd_values)
            if active_fwd_values
            else 1.0
        )

        stressed_count = 0
        for sid in near_sink_nodes:
            fwd = recent_fwd_map.get(sid, 0)
            load_factor = fwd / mean_fwd if mean_fwd > 0 else 0.0
            if load_factor >= self.overload_factor:
                stressed_count += 1

        overloaded_ratio = stressed_count / len(near_sink_nodes)
        alert_load = overloaded_ratio >= self.overloaded_ratio_threshold

        # ---------------------------------------------------------
        # TÍN HIỆU 2: Energy Drain Rate (D_i)
        # ---------------------------------------------------------
        drain_map: Dict[int, float] = {}
        for sid, e_hist in self.energy_history.items():
            if len(e_hist) >= 2:
                drain_rate = (e_hist[0] - e_hist[-1]) / (len(e_hist) - 1)
                drain_map[sid] = max(0.0, drain_rate)
            else:
                drain_map[sid] = 0.0

        near_drains = [drain_map.get(sid, 0.0) for sid in near_sink_nodes]
        mean_near_drain = (
            sum(near_drains) / len(near_drains)
            if near_drains
            else 0.0
        )

        network_drains = [d for d in drain_map.values() if d > 0]
        mean_network_drain = (
            sum(network_drains) / len(network_drains)
            if network_drains
            else 0.0
        )

        if mean_network_drain > 1e-6:
            drain_ratio = mean_near_drain / mean_network_drain
        else:
            drain_ratio = 1.0

        alert_drain = drain_ratio >= self.drain_ratio_threshold

        # ---------------------------------------------------------
        # TÍN HIỆU 3: Route Concentration (C_i)
        # ---------------------------------------------------------
        concentration_map = self.compute_route_concentration(route_table)
        near_concentrations = [
            concentration_map.get(sid, 0.0)
            for sid in near_sink_nodes
        ]
        max_concentration = (
            max(near_concentrations)
            if near_concentrations
            else 0.0
        )
        alert_concentration = (
            max_concentration >= self.route_concentration_threshold
        )

        # ---------------------------------------------------------
        # TỔNG HỢP: Ít nhất 2 trong 3 tín hiệu cảnh báo
        # ---------------------------------------------------------
        active_alerts_count = (
            int(alert_load)
            + int(alert_drain)
            + int(alert_concentration)
        )
        should_alert = active_alerts_count >= 2

        snapshot = SinkStressSnapshot(
            round_number=current_round,
            near_sink_nodes_count=len(near_sink_nodes),
            stressed_relays_count=stressed_count,
            overloaded_ratio=overloaded_ratio,
            drain_ratio=drain_ratio,
            max_route_concentration=max_concentration,
            alert_load=alert_load,
            alert_drain=alert_drain,
            alert_concentration=alert_concentration,
            active_alerts_count=active_alerts_count,
            should_alert=should_alert
        )
        self.last_snapshot = snapshot
        return snapshot
