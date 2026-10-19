from dataclasses import dataclass
import math
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx

from core.sink import SinkNode
from mobility.sink_stress_monitor import SinkStressMonitor, SinkStressSnapshot
from routing.ecmhr import ECMHRRouter


@dataclass
class Waypoint:
    idx: int
    x: float
    y: float
    name: str

    @property
    def pos(self) -> Tuple[float, float]:
        return (self.x, self.y)


@dataclass
class SinkDecision:
    evaluated: bool
    moved: bool
    current_round: int
    from_waypoint: int | str
    to_waypoint: int | str
    from_pos: Tuple[float, float]
    to_pos: Tuple[float, float]
    distance_m: float
    reason: str
    stress_snapshot: Optional[SinkStressSnapshot] = None
    cost_current: float = 0.0
    cost_best: float = 0.0
    improvement_ratio: float = 0.0


class AdaptiveSinkController:
    """
    Bộ điều khiển Constrained Adaptive Dynamic Mobile Sink:
    - Giám sát áp lực mạng thông qua SinkStressMonitor (Early warning 3 tín hiệu: Overload, Drain, Route Concentration).
    - Khi có stress kéo dài (persistence >= 2 chu kỳ) và thỏa mãn dwell time:
      + Tự động sinh không gian vị trí ứng viên động (Dynamic Candidates):
        * Bán kính r in {400, 550, 700}m, 12 hướng = 36 candidate xung quanh Sink.
        * Lọc miền an toàn biên mạng (boundary_margin_m, mặc định [200, 1800]m).
        * Lọc khoảng cách di chuyển (min_move_distance_m <= d <= max_move_distance_m).
        * Lọc cơ chế Tabu: cấm các vị trí trong bán kính tabu_radius_m của các vị trí rời đi trong return_tabu_rounds.
      + Dry-run ECMHR routing giả lập cho từng candidate và vị trí hiện tại để tính hàm chi phí:
        J(S_k) = 0.40 * C_norm + 0.25 * L_norm + 0.20 * D_norm + 0.10 * H_norm + 0.05 * M_norm
      + Áp dụng ngưỡng cải thiện tối thiểu (minimum_improvement_ratio = 10%):
        (J_curr - J_best) / J_curr >= 0.10.
        Nếu không đạt 10% -> STAY (tránh di chuyển vụn vặt và triệt tiêu dao động ping-pong).
        Nếu đạt -> MOVE đến S* và thêm vị trí cũ vào Tabu.
    """

    def __init__(
        self,
        network,
        config: dict
    ):
        self.network = network
        self.config = config

        mobile_config = config.get("mobile_sink", {})
        self.enabled = bool(mobile_config.get("enabled", True))
        self.mode = str(mobile_config.get("mode", "adaptive_dynamic"))

        self.evaluation_interval_rounds = int(
            mobile_config.get("evaluation_interval_rounds", 6)
        )
        self.trigger_persistence = int(
            mobile_config.get("trigger_persistence", 2)
        )
        self.minimum_dwell_rounds = int(
            mobile_config.get("minimum_dwell_rounds", 24)
        )
        self.cooldown_rounds = int(
            mobile_config.get("cooldown_rounds", 24)
        )

        # Cấu hình dynamic candidate
        raw_radii = mobile_config.get("candidate_radii_m")
        if raw_radii and isinstance(raw_radii, list):
            self.candidate_radii_m = [float(r) for r in raw_radii]
        elif "movement_radius_m" in mobile_config:
            self.candidate_radii_m = [float(mobile_config["movement_radius_m"])]
        else:
            self.candidate_radii_m = [400.0, 550.0, 700.0]

        self.candidate_directions = int(
            mobile_config.get("candidate_directions", 12)
        )
        self.boundary_margin_m = float(
            mobile_config.get("boundary_margin_m", 200.0)
        )
        self.min_move_distance_m = float(
            mobile_config.get("min_move_distance_m", 400.0)
        )
        self.max_move_distance_m = float(
            mobile_config.get("max_move_distance_m", 700.0)
        )
        self.return_tabu_rounds = int(
            mobile_config.get("return_tabu_rounds", 72)
        )
        self.tabu_radius_m = float(
            mobile_config.get("tabu_radius_m", 300.0)
        )
        self.minimum_improvement_ratio = float(
            mobile_config.get("minimum_improvement_ratio", 0.10)
        )

        # Tabu history: danh sách các tuple (x, y, round_left)
        self.tabu_history: List[Tuple[float, float, int]] = []

        sink_x = float(getattr(self.network.sink, "x", config.get("sink", {}).get("x", 1000.0)))
        sink_y = float(getattr(self.network.sink, "y", config.get("sink", {}).get("y", 1000.0)))
        self.current_waypoint_idx: int | str = 0
        self.current_waypoint_name: str = "W0_Center"
        self.last_move_round = 0
        self.consecutive_alerts = 0
        self.movement_history: List[SinkDecision] = []
        self.last_snapshot: Optional[SinkStressSnapshot] = None

        # Sinh các candidate động ban đầu quanh vị trí Sink hiện tại
        self.candidate_waypoints = self.generate_dynamic_candidates(
            cur_x=sink_x,
            cur_y=sink_y,
            current_round=0
        )

        # Khởi tạo Stress Monitor
        self.stress_monitor = SinkStressMonitor(
            network=network,
            load_window_rounds=int(mobile_config.get("load_window_rounds", 24)),
            overload_factor=float(mobile_config.get("overload_factor", 1.8)),
            overloaded_ratio_threshold=float(
                mobile_config.get("overloaded_ratio_threshold", 0.30)
            ),
            drain_ratio_threshold=float(
                mobile_config.get("drain_ratio_threshold", 1.50)
            ),
            route_concentration_threshold=float(
                mobile_config.get("route_concentration_threshold", 0.30)
            )
        )

    @property
    def waypoints(self) -> List[Waypoint]:
        """
        Trả về danh sách waypoint ứng viên phục vụ hiển thị UI và tương thích ngược.
        Bao gồm vị trí hiện tại (W0) và các dynamic candidates.
        """
        cur_pos = (self.network.sink.x, self.network.sink.y)
        cur_wp = Waypoint(
            idx=0,
            x=cur_pos[0],
            y=cur_pos[1],
            name=str(self.current_waypoint_name)
        )
        return [cur_wp] + self.candidate_waypoints

    def record_round(self, current_round: int) -> None:
        """
        Ghi nhận dữ liệu round cho stress monitor.
        """
        if self.enabled:
            self.stress_monitor.record_round(current_round)

    def generate_dynamic_candidates(
        self,
        cur_x: float,
        cur_y: float,
        current_round: int
    ) -> List[Waypoint]:
        """
        Sinh không gian vị trí ứng viên động quanh tọa độ Sink hiện tại:
        - Quét theo candidate_radii_m và candidate_directions.
        - Lọc các điểm ngoài miền an toàn (boundary_margin_m).
        - Lọc các điểm ngoài khoảng cự ly [min_move_distance_m, max_move_distance_m].
        - Lọc các điểm nằm trong vùng Tabu của các vị trí rời đi < return_tabu_rounds.
        """
        net_cfg = self.config.get("network", {})
        width_m = float(getattr(self.network, "width_m", None) or net_cfg.get("width_m", net_cfg.get("area_width_m", 2000.0)))
        height_m = float(getattr(self.network, "height_m", None) or net_cfg.get("height_m", net_cfg.get("area_height_m", 2000.0)))

        min_x = self.boundary_margin_m
        max_x = max(min_x, width_m - self.boundary_margin_m)
        min_y = self.boundary_margin_m
        max_y = max(min_y, height_m - self.boundary_margin_m)

        # Lọc các entry tabu còn hiệu lực
        active_tabu = [
            (tx, ty, r_left)
            for tx, ty, r_left in self.tabu_history
            if (current_round - r_left) < self.return_tabu_rounds
        ]

        candidates: List[Waypoint] = []
        cand_idx = 1

        for r in self.candidate_radii_m:
            for d in range(self.candidate_directions):
                angle = d * (2.0 * math.pi / self.candidate_directions)
                cand_x = round(cur_x + r * math.cos(angle), 2)
                cand_y = round(cur_y + r * math.sin(angle), 2)

                # 1. Kiểm tra miền an toàn (Boundary check)
                if not (min_x <= cand_x <= max_x and min_y <= cand_y <= max_y):
                    continue

                # 2. Kiểm tra khoảng cách di chuyển
                dist = math.hypot(cand_x - cur_x, cand_y - cur_y)
                if dist < (self.min_move_distance_m - 1.0) or dist > (self.max_move_distance_m + 1.0):
                    continue

                # 3. Kiểm tra điều kiện Tabu
                is_tabu = False
                for tx, ty, _ in active_tabu:
                    if math.hypot(cand_x - tx, cand_y - ty) < self.tabu_radius_m:
                        is_tabu = True
                        break
                if is_tabu:
                    continue

                deg = int(math.degrees(angle)) % 360
                candidates.append(
                    Waypoint(
                        idx=cand_idx,
                        x=cand_x,
                        y=cand_y,
                        name=f"C{cand_idx}_{int(r)}m_{deg}deg"
                    )
                )
                cand_idx += 1

        return candidates

    def _evaluate_point_metrics(
        self,
        x: float,
        y: float,
        cur_x: float,
        cur_y: float,
        route_manager
    ) -> Dict[str, Any]:
        """
        Thực hiện Dry-run ECMHR và tính 5 chỉ số thô:
        - avg_hop: Số hop trung bình H
        - max_conc: Độ hội tụ route lớn nhất C
        - load: Tải gần đây của các relay dự kiến phục vụ Sink L
        - depletion: Mức tiêu hao năng lượng trung bình của các relay dự kiến D
        - dist_move: Khoảng cách di chuyển từ vị trí hiện tại M
        """
        dist_move = math.hypot(x - cur_x, y - cur_y)
        energy_threshold_ratio = getattr(
            route_manager, "energy_threshold_ratio", 0.15
        )

        # 1. Tìm các relay dự kiến phục vụ Sink nếu đặt tại (x, y)
        serving_relays = [
            sensor for sensor in self.network.sensors
            if math.hypot(sensor.x - x, sensor.y - y) <= sensor.transmission_range
            and sensor.is_alive()
        ]

        if not serving_relays:
            return {
                "avg_hop": 20.0,
                "max_conc": 1.0,
                "load": 1e6,
                "depletion": 1.0,
                "dist_move": dist_move,
                "valid": False
            }

        # 2. Tải gần đây (L) và Energy Depletion (D) của serving relays
        load_list = [
            self.stress_monitor.get_node_forwarded_in_window(s.node_id)
            for s in serving_relays
        ]
        avg_load = sum(load_list) / len(load_list) if load_list else 0.0

        depletion_list = [
            (s.initial_energy - s.remaining_energy) / s.initial_energy
            for s in serving_relays
        ]
        avg_depletion = sum(depletion_list) / len(depletion_list) if depletion_list else 0.0

        # 3. Dry-run ECMHR routing
        temp_sink = SinkNode(x=x, y=y, node_id="TEMP_SINK")
        temp_graph = self.network.graph.copy()
        if self.network.sink.node_id in temp_graph:
            temp_graph.remove_node(self.network.sink.node_id)

        temp_graph.add_node("TEMP_SINK", pos=(x, y))
        for sensor in serving_relays:
            d = math.hypot(sensor.x - x, sensor.y - y)
            temp_graph.add_edge(sensor.node_id, "TEMP_SINK", distance=d)

        class _TempNetwork:
            def __init__(self, sensors, sink, graph):
                self.sensors = sensors
                self.sink = sink
                self.graph = graph

        temp_net = _TempNetwork(self.network.sensors, temp_sink, temp_graph)
        temp_router = ECMHRRouter(
            network=temp_net,
            energy_threshold_ratio=energy_threshold_ratio
        )
        temp_routes = temp_router.build_route_table()

        # 4. Tính số hop trung bình H và độ hội tụ C
        hop_counts = [
            r.hop_count for r in temp_routes.values()
            if r is not None and getattr(r, "hop_count", None)
        ]
        avg_hop = (
            sum(hop_counts) / len(hop_counts)
            if hop_counts
            else 20.0
        )

        relay_counts: Dict[int, int] = {}
        valid_cnt = len(hop_counts)
        for r in temp_routes.values():
            if r is not None and getattr(r, "path", None):
                for relay in r.path[1:-1]:
                    if isinstance(relay, int):
                        relay_counts[relay] = relay_counts.get(relay, 0) + 1

        max_conc = (
            max(relay_counts.values()) / valid_cnt
            if valid_cnt > 0 and relay_counts
            else 0.0
        )

        return {
            "avg_hop": avg_hop,
            "max_conc": max_conc,
            "load": avg_load,
            "depletion": avg_depletion,
            "dist_move": dist_move,
            "valid": True
        }

    def _dry_run_score_candidates(
        self,
        current_round: int,
        route_manager,
        candidates: List[Waypoint]
    ) -> Tuple[Optional[Waypoint], float, float, float]:
        """
        Đánh giá các candidate và vị trí hiện tại bằng hàm score J:
        J(S_k) = 0.40 * C_norm + 0.25 * L_norm + 0.20 * D_norm + 0.10 * H_norm + 0.05 * M_norm

        Trả về:
        (best_candidate, cost_current, cost_best, improvement_ratio)
        """
        cur_sink_pos = (self.network.sink.x, self.network.sink.y)

        # Đánh giá vị trí hiện tại
        curr_metrics = self._evaluate_point_metrics(
            x=cur_sink_pos[0],
            y=cur_sink_pos[1],
            cur_x=cur_sink_pos[0],
            cur_y=cur_sink_pos[1],
            route_manager=route_manager
        )

        # Đánh giá các candidates
        cand_metrics_list = []
        for wp in candidates:
            m = self._evaluate_point_metrics(
                x=wp.x,
                y=wp.y,
                cur_x=cur_sink_pos[0],
                cur_y=cur_sink_pos[1],
                route_manager=route_manager
            )
            m["wp"] = wp
            cand_metrics_list.append(m)

        all_points = [curr_metrics] + cand_metrics_list

        def _normalize(values: List[float]) -> List[float]:
            mn, mx = min(values), max(values)
            if mx - mn < 1e-6:
                return [0.5 if mn > 0 else 0.0 for _ in values]
            return [(v - mn) / (mx - mn) for v in values]

        norm_concs = _normalize([p["max_conc"] for p in all_points])
        norm_loads = _normalize([p["load"] for p in all_points])
        norm_depls = _normalize([p["depletion"] for p in all_points])
        norm_hops = _normalize([p["avg_hop"] for p in all_points])
        norm_moves = _normalize([p["dist_move"] for p in all_points])

        def _calc_cost(idx: int) -> float:
            return (
                0.40 * norm_concs[idx]
                + 0.25 * norm_loads[idx]
                + 0.20 * norm_depls[idx]
                + 0.10 * norm_hops[idx]
                + 0.05 * norm_moves[idx]
            )

        j_current = _calc_cost(0)

        best_wp: Optional[Waypoint] = None
        j_best = float("inf")

        for k, cm in enumerate(cand_metrics_list):
            cand_cost = _calc_cost(k + 1)
            cm["cost"] = cand_cost
            if cand_cost < j_best:
                j_best = cand_cost
                best_wp = cm["wp"]

        if best_wp is None or j_best == float("inf"):
            return None, j_current, j_current, 0.0

        improvement_ratio = (
            (j_current - j_best) / j_current
            if j_current > 1e-6
            else 0.0
        )

        return best_wp, j_current, j_best, improvement_ratio

    def evaluate_and_step(
        self,
        current_round: Optional[int] = None,
        route_manager=None,
        round_num: Optional[int] = None
    ) -> SinkDecision:
        """
        Đánh giá và ra quyết định STAY hoặc MOVE cho Sink:
        1. Kiểm tra chu kỳ đánh giá (evaluation_interval_rounds).
        2. Đánh giá 3 tín hiệu cảnh báo sớm từ Stress Monitor.
        3. Kiểm tra điều kiện Dwell Time & Trigger Persistence.
        4. Sinh không gian Candidate động (Dynamic Candidate Search).
        5. Lọc miền an toàn, khoảng cách di chuyển và Tabu.
        6. Chạy Dry-run ECMHR và tính điểm Cost J.
        7. Kiểm tra Minimum Improvement (10%). Nếu thỏa mãn -> MOVE; ngược lại -> STAY.
        """
        if current_round is None:
            current_round = round_num if round_num is not None else 0

        cur_pos = (self.network.sink.x, self.network.sink.y)

        if not self.enabled:
            return SinkDecision(
                evaluated=False,
                moved=False,
                current_round=current_round,
                from_waypoint=self.current_waypoint_name,
                to_waypoint=self.current_waypoint_name,
                from_pos=cur_pos,
                to_pos=cur_pos,
                distance_m=0.0,
                reason="Mobile Sink disabled"
            )

        if current_round % self.evaluation_interval_rounds != 0:
            return SinkDecision(
                evaluated=False,
                moved=False,
                current_round=current_round,
                from_waypoint=self.current_waypoint_name,
                to_waypoint=self.current_waypoint_name,
                from_pos=cur_pos,
                to_pos=cur_pos,
                distance_m=0.0,
                reason="Not in evaluation round"
            )

        # 1. Đánh giá 3 tín hiệu áp lực từ Stress Monitor
        snapshot = self.stress_monitor.evaluate(
            current_round=current_round,
            route_table=route_manager.route_table if route_manager else {}
        )
        self.last_snapshot = snapshot

        if snapshot.should_alert:
            self.consecutive_alerts += 1
        else:
            self.consecutive_alerts = 0

        # 2. Kiểm tra Dwell Time & Persistence
        rounds_since_last_move = current_round - self.last_move_round
        in_dwell = rounds_since_last_move < self.minimum_dwell_rounds

        can_move = (
            self.consecutive_alerts >= self.trigger_persistence
            and not in_dwell
        )

        if not can_move:
            stay_reason = (
                f"STAY: in_dwell ({rounds_since_last_move}/{self.minimum_dwell_rounds}r)"
                if in_dwell
                else f"STAY: persistence {self.consecutive_alerts}/{self.trigger_persistence} alerts"
            )
            return SinkDecision(
                evaluated=True,
                moved=False,
                current_round=current_round,
                from_waypoint=self.current_waypoint_name,
                to_waypoint=self.current_waypoint_name,
                from_pos=cur_pos,
                to_pos=cur_pos,
                distance_m=0.0,
                reason=stay_reason,
                stress_snapshot=snapshot
            )

        # 3. Sinh các Dynamic Candidates
        candidates = self.generate_dynamic_candidates(
            cur_x=cur_pos[0],
            cur_y=cur_pos[1],
            current_round=current_round
        )
        self.candidate_waypoints = candidates

        if not candidates:
            return SinkDecision(
                evaluated=True,
                moved=False,
                current_round=current_round,
                from_waypoint=self.current_waypoint_name,
                to_waypoint=self.current_waypoint_name,
                from_pos=cur_pos,
                to_pos=cur_pos,
                distance_m=0.0,
                reason="STAY: No valid dynamic candidates (boundary/tabu/distance constraints)",
                stress_snapshot=snapshot
            )

        # 4. Dry-run ECMHR và chấm điểm
        best_wp, j_curr, j_best, imp_ratio = self._dry_run_score_candidates(
            current_round=current_round,
            route_manager=route_manager,
            candidates=candidates
        )

        # 5. Kiểm tra Minimum Improvement (ngưỡng 10%)
        if best_wp is None or imp_ratio < self.minimum_improvement_ratio:
            return SinkDecision(
                evaluated=True,
                moved=False,
                current_round=current_round,
                from_waypoint=self.current_waypoint_name,
                to_waypoint=self.current_waypoint_name,
                from_pos=cur_pos,
                to_pos=cur_pos,
                distance_m=0.0,
                reason=(
                    f"STAY: Improvement {imp_ratio:.1%} < {self.minimum_improvement_ratio:.0%} "
                    f"(Current J={j_curr:.3f}, Best J={j_best:.3f})"
                ),
                stress_snapshot=snapshot,
                cost_current=j_curr,
                cost_best=j_best,
                improvement_ratio=imp_ratio
            )

        # 6. Đủ điều kiện -> Thực hiện MOVE
        old_name = self.current_waypoint_name
        old_pos = cur_pos

        # Ghi nhận vị trí cũ vào Tabu List
        self.tabu_history.append((old_pos[0], old_pos[1], current_round))

        # Di chuyển Sink
        dist = self.network.sink.move_to(
            new_x=best_wp.x,
            new_y=best_wp.y,
            waypoint_id=best_wp.name,
            round_num=current_round,
            reason=(
                f"Adaptive Move: J improved {imp_ratio:.1%} (J: {j_curr:.3f}->{j_best:.3f}), "
                f"Overload={snapshot.overloaded_ratio:.0%}, Drain={snapshot.drain_ratio:.2f}x, "
                f"Conc={snapshot.max_route_concentration:.0%}"
            )
        )
        self.network.update_sink_position(best_wp.x, best_wp.y)

        self.current_waypoint_idx = best_wp.idx
        self.current_waypoint_name = best_wp.name
        self.last_move_round = current_round
        self.consecutive_alerts = 0

        # Làm mới bảng định tuyến
        if route_manager:
            route_manager.clear()

        decision = SinkDecision(
            evaluated=True,
            moved=True,
            current_round=current_round,
            from_waypoint=old_name,
            to_waypoint=best_wp.name,
            from_pos=old_pos,
            to_pos=best_wp.pos,
            distance_m=dist,
            reason=(
                f"MOVE to {best_wp.name}: J improved {imp_ratio:.1%} "
                f"(J: {j_curr:.3f} -> {j_best:.3f}, dist={dist:.1f}m)"
            ),
            stress_snapshot=snapshot,
            cost_current=j_curr,
            cost_best=j_best,
            improvement_ratio=imp_ratio
        )
        self.movement_history.append(decision)
        return decision
