from typing import Dict, Optional

from routing.ecmhr import (
    ECMHRRouter,
    ECMHRRouteResult
)
from routing.minimum_hop import (
    find_minimum_hop_route
)
from routing.route_table import (
    build_minimum_hop_route_table
)


class RouteManager:
    """
    Quản lý bảng định tuyến mạng, hỗ trợ Minimum-Hop và ECMHR.
    Tự động tái sử dụng (cache hit) và chỉ xây dựng lại khi:
    - Sink đổi vị trí (do Mobile Sink di chuyển)
    - Có node cạn pin chết
    - Có node chuyển sang trạng thái LOW_ENERGY (đối với ECMHR)
    - Đến chu kỳ cập nhật định kỳ (route_update_interval_rounds)
    """

    def __init__(
        self,
        network,
        config,
        algorithm="ecmhr"
    ):
        self.network = network
        self.config = config

        routing_config = config.get("routing", {})
        ecmhr_config = routing_config.get("ecmhr", {})

        self.algorithm = (
            algorithm
            or routing_config.get("algorithm", "ecmhr")
        )
        if self.algorithm == "lb_ecmhr":
            self.algorithm = "ecmhr"

        self.routing_algorithm = self.algorithm

        self.energy_threshold_ratio = float(
            routing_config.get(
                "energy_threshold_ratio",
                config.get("sensor", {}).get("energy_threshold_ratio", 0.15)
            )
        )

        self.route_table: Dict[int, Optional[object]] = {}

        self.route_requests = 0
        self.route_table_hits = 0
        self.route_table_builds = 0
        self.on_demand_reroutes = 0

        self.sensor_map = {
            sensor.node_id: sensor
            for sensor in network.sensors
        }

        self.route_update_interval_rounds = int(
            ecmhr_config.get(
                "route_update_interval_rounds",
                routing_config.get("route_update_interval_rounds", 6)
            )
        )

        self.last_build_round = -999
        self.prev_low_energy_nodes = set()
        self.prev_dead_nodes = set()
        self._last_sink_position = (network.sink.x, network.sink.y)
        self._round_counter = 0

        self.ecmhr_router = ECMHRRouter(
            network=network,
            energy_threshold_ratio=self.energy_threshold_ratio
        )

    def set_algorithm(self, algorithm: str):
        if algorithm == "lb_ecmhr":
            algorithm = "ecmhr"

        if algorithm not in {"minimum_hop", "ecmhr"}:
            raise ValueError(
                f"Unsupported routing algorithm: {algorithm}. "
                f"Supported: ['minimum_hop', 'ecmhr']"
            )

        self.algorithm = algorithm
        self.routing_algorithm = algorithm
        self.clear()

    def clear(self):
        self.route_table = {}
        self.last_build_round = -999
        self.prev_low_energy_nodes = set()
        self.prev_dead_nodes = set()
        self._last_sink_position = (self.network.sink.x, self.network.sink.y)

    def _active_minimum_hop_graph(self):
        graph = self.network.graph.copy()
        dead_nodes = [
            sensor.node_id
            for sensor in self.network.sensors
            if not sensor.is_alive()
        ]
        graph.remove_nodes_from(dead_nodes)
        return graph

    def _build_minimum_hop_table(self):
        graph = self._active_minimum_hop_graph()
        sensor_ids = [sensor.node_id for sensor in self.network.sensors]
        self.route_table = build_minimum_hop_route_table(
            graph=graph,
            sensor_ids=sensor_ids,
            sink_id=self.network.sink.node_id
        )
        self.route_table_builds += 1

    def prepare_round(self, current_round: Optional[int] = None):
        """
        Xây dựng hoặc tái sử dụng bảng định tuyến theo trạng thái năng lượng
        và vị trí Sink hiện tại.
        """
        if current_round is None:
            self._round_counter += 1
            current_round = self._round_counter

        current_sink_pos = (self.network.sink.x, self.network.sink.y)
        sink_moved = (current_sink_pos != getattr(self, "_last_sink_position", None))

        dead_nodes = {
            sensor.node_id
            for sensor in self.network.sensors
            if not sensor.is_alive()
        }
        node_died = (dead_nodes != self.prev_dead_nodes)

        interval_elapsed = (
            (current_round - self.last_build_round)
            >= self.route_update_interval_rounds
        )

        if self.algorithm == "minimum_hop":
            should_rebuild = (
                not self.route_table
                or sink_moved
                or node_died
                or interval_elapsed
            )

            if should_rebuild:
                self._build_minimum_hop_table()
                self.last_build_round = current_round
                self.prev_dead_nodes = dead_nodes
                self._last_sink_position = current_sink_pos
            return

        if self.algorithm == "ecmhr":
            low_energy_nodes = {
                sensor.node_id
                for sensor in self.network.sensors
                if sensor.is_alive()
                and (sensor.energy_ratio() <= self.energy_threshold_ratio)
            }
            energy_state_changed = (low_energy_nodes != self.prev_low_energy_nodes)

            should_rebuild = (
                not self.route_table
                or sink_moved
                or node_died
                or energy_state_changed
                or interval_elapsed
            )

            if should_rebuild:
                self.route_table = self.ecmhr_router.build_route_table()
                self.route_table_builds += 1
                self.last_build_round = current_round
                self.prev_low_energy_nodes = low_energy_nodes
                self.prev_dead_nodes = dead_nodes
                self._last_sink_position = current_sink_pos
            return

        raise ValueError(f"Unknown routing algorithm: {self.algorithm}")

    def _route_is_valid(self, route) -> bool:
        if route is None:
            return False

        if not getattr(route, "path", None):
            return False

        if len(route.path) < 2:
            return False

        source_id = route.path[0]
        if source_id not in self.sensor_map:
            return False

        source = self.sensor_map[source_id]
        if not source.is_alive():
            return False

        # Các node trung gian (relays)
        relay_ids = route.path[1:-1]
        for relay_id in relay_ids:
            relay = self.sensor_map.get(relay_id)
            if relay is None or not relay.is_alive():
                return False

            if self.algorithm == "ecmhr":
                if relay.energy_ratio() <= self.energy_threshold_ratio:
                    return False

        # Các liên kết vật lý phải còn tồn tại trên đồ thị
        for index in range(len(route.path) - 1):
            if not self.network.graph.has_edge(
                route.path[index],
                route.path[index + 1]
            ):
                return False

        return True

    def is_route_valid(self, route) -> bool:
        return self._route_is_valid(route)

    def _reroute(self, source_id: int):
        self.on_demand_reroutes += 1

        if self.algorithm == "minimum_hop":
            graph = self._active_minimum_hop_graph()
            return find_minimum_hop_route(
                graph=graph,
                source_id=source_id,
                sink_id=self.network.sink.node_id
            )

        return self.ecmhr_router.route_source(source_id=source_id)

    def get_route(self, source_id: int):
        self.route_requests += 1

        if source_id in self.route_table:
            route = self.route_table[source_id]
            if route is None:
                return None
            if self._route_is_valid(route):
                self.route_table_hits += 1
                return route

        route = self._reroute(source_id)
        self.route_table[source_id] = route
        return route

    def get_metrics(self) -> dict:
        if self.route_requests > 0:
            hit_ratio = self.route_table_hits / self.route_requests
        else:
            hit_ratio = 0.0

        return {
            "routing_requests": self.route_requests,
            "route_table_hits": self.route_table_hits,
            "route_table_builds": self.route_table_builds,
            "routing_reroutes": self.on_demand_reroutes,
            "route_cache_hit_ratio": hit_ratio
        }