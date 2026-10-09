from routing.lb_ecmhr import (
    LBECMHRRouter,
    LBECMHRRouteResult
)
from routing.load_tracker import (
    RelayLoadTracker
)
from routing.minimum_hop import (
    find_minimum_hop_route
)
from routing.route_table import (
    build_minimum_hop_route_table
)


class RouteManager:

    def __init__(
        self,
        network,
        config,
        algorithm="lb_ecmhr"
    ):

        self.network = network
        self.config = config

        routing_config = (
            config.get(
                "routing",
                {}
            )
        )

        lb_config = (
            routing_config.get(
                "lb_ecmhr",
                {}
            )
        )

        self.algorithm = (
            algorithm
            or routing_config.get(
                "algorithm",
                "lb_ecmhr"
            )
        )

        self.routing_algorithm = self.algorithm

        self.energy_threshold_ratio = float(
            routing_config.get(
                "energy_threshold_ratio",
                config.get(
                    "sensor",
                    {}
                ).get(
                    "energy_threshold_ratio",
                    0.20
                )
            )
        )

        self.route_table = {}

        self.route_requests = 0
        self.route_table_hits = 0
        self.route_table_builds = 0
        self.on_demand_reroutes = 0

        self.sensor_map = {
            sensor.node_id: sensor
            for sensor in network.sensors
        }

        self.load_tracker = RelayLoadTracker(
            window_rounds=int(
                lb_config.get(
                    "load_window_rounds",
                    20
                )
            ),
            overload_factor=float(
                lb_config.get(
                    "overload_factor",
                    2.0
                )
            ),
            recovery_factor=float(
                lb_config.get(
                    "recovery_factor",
                    1.2
                )
            )
        )

        self.route_update_interval_rounds = int(
            lb_config.get(
                "route_update_interval_rounds",
                6
            )
        )

        self.candidate_routes_per_source = int(
            lb_config.get(
                "candidate_routes_per_source",
                6
            )
        )

        self.last_build_round = -999
        self.prev_overloaded_nodes = set()
        self.prev_low_energy_nodes = set()
        self.prev_dead_nodes = set()
        self._round_counter = 0

        self.lb_ecmhr_router = LBECMHRRouter(
            network=network,
            energy_threshold_ratio=(
                self.energy_threshold_ratio
            ),
            max_extra_hops=int(
                lb_config.get(
                    "max_extra_hops",
                    1
                )
            ),
            allow_overload_fallback=bool(
                lb_config.get(
                    "allow_overload_fallback",
                    True
                )
            ),
            candidate_k=self.candidate_routes_per_source
        )

    def set_algorithm(
        self,
        algorithm
    ):

        if algorithm not in {
            "minimum_hop",
            "lb_ecmhr"
        }:

            raise ValueError(
                f"Unsupported routing algorithm: "
                f"{algorithm}"
            )

        self.algorithm = algorithm
        self.routing_algorithm = algorithm

        self.clear()

    def clear(self):

        self.route_table = {}
        self.last_build_round = -999
        self.prev_overloaded_nodes = set()
        self.prev_low_energy_nodes = set()
        self.prev_dead_nodes = set()

    def _active_minimum_hop_graph(self):

        graph = (
            self.network.graph.copy()
        )

        dead_nodes = [
            sensor.node_id
            for sensor
            in self.network.sensors
            if not sensor.is_alive()
        ]

        graph.remove_nodes_from(
            dead_nodes
        )

        return graph

    def _build_minimum_hop_table(self):

        graph = (
            self._active_minimum_hop_graph()
        )

        sensor_ids = [
            sensor.node_id
            for sensor
            in self.network.sensors
        ]

        self.route_table = (
            build_minimum_hop_route_table(
                graph=graph,
                sensor_ids=sensor_ids,
                sink_id=(
                    self.network
                    .sink
                    .node_id
                )
            )
        )

        self.route_table_builds += 1

    def prepare_round(
        self,
        current_round: int | None = None
    ):
        """
        Build or reuse routes using the current energy/load snapshot.
        Rebuilds when the update interval has elapsed or when network state
        changes (overload state, low energy transition, node death).
        """
        if current_round is None:
            self._round_counter += 1
            current_round = self._round_counter

        dead_nodes = {
            sensor.node_id
            for sensor
            in self.network.sensors
            if not sensor.is_alive()
        }
        node_died = (dead_nodes != self.prev_dead_nodes)

        if (
            self.algorithm
            == "minimum_hop"
        ):
            interval_elapsed = (
                (current_round - self.last_build_round)
                >= self.route_update_interval_rounds
            )
            should_rebuild = (
                not self.route_table
                or node_died
                or interval_elapsed
            )

            if should_rebuild:
                self._build_minimum_hop_table()
                self.last_build_round = current_round
                self.prev_dead_nodes = dead_nodes
            return

        if (
            self.algorithm
            == "lb_ecmhr"
        ):
            # Load reflects preceding rounds
            self.load_tracker.update(
                self.network.sensors
            )

            overloaded_nodes = set(
                self.load_tracker.overloaded_nodes
            )
            low_energy_nodes = {
                sensor.node_id
                for sensor
                in self.network.sensors
                if sensor.is_alive()
                and (
                    sensor.energy_ratio()
                    <= self.energy_threshold_ratio
                )
            }

            overload_state_changed = (
                overloaded_nodes != self.prev_overloaded_nodes
            )
            energy_state_changed = (
                low_energy_nodes != self.prev_low_energy_nodes
            )
            interval_elapsed = (
                (current_round - self.last_build_round)
                >= self.route_update_interval_rounds
            )

            should_rebuild = (
                not self.route_table
                or interval_elapsed
                or overload_state_changed
                or energy_state_changed
                or node_died
            )

            if should_rebuild:
                self.route_table = (
                    self.lb_ecmhr_router
                    .build_route_table(
                        load_factors=(
                            self.load_tracker
                            .load_factors
                        ),
                        overloaded_nodes=(
                            overloaded_nodes
                        )
                    )
                )
                self.route_table_builds += 1
                self.last_build_round = current_round
                self.prev_overloaded_nodes = overloaded_nodes
                self.prev_low_energy_nodes = low_energy_nodes
                self.prev_dead_nodes = dead_nodes
            return

        raise ValueError(
            f"Unknown routing algorithm: "
            f"{self.algorithm}"
        )

    def _route_is_valid(
        self,
        route
    ) -> bool:

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

        # Intermediate nodes (relays) only
        relay_ids = route.path[1:-1]

        for relay_id in relay_ids:

            relay = self.sensor_map.get(
                relay_id
            )

            if relay is None:
                return False

            if not relay.is_alive():
                return False

            if (
                self.algorithm
                == "lb_ecmhr"
            ):

                if (
                    relay.energy_ratio()
                    <= self.energy_threshold_ratio
                ):

                    return False

        # Physical links must still exist
        for index in range(
            len(route.path) - 1
        ):

            if not (
                self.network.graph.has_edge(
                    route.path[index],
                    route.path[index + 1]
                )
            ):

                return False

        return True

    def is_route_valid(
        self,
        route
    ) -> bool:

        return self._route_is_valid(route)

    def _reroute(
        self,
        source_id
    ):

        self.on_demand_reroutes += 1

        if (
            self.algorithm
            == "minimum_hop"
        ):

            graph = (
                self._active_minimum_hop_graph()
            )

            return find_minimum_hop_route(
                graph=graph,
                source_id=source_id,
                sink_id=(
                    self.network
                    .sink
                    .node_id
                )
            )

        return self.lb_ecmhr_router.route_source(
            source_id=source_id,
            load_factors=(
                self.load_tracker.load_factors
            ),
            overloaded_nodes=(
                self.load_tracker.overloaded_nodes
            )
        )

    def get_route(
        self,
        source_id
    ):

        self.route_requests += 1

        if source_id in self.route_table:
            route = self.route_table[source_id]
            if route is None:
                return None
            if self._route_is_valid(route):
                self.route_table_hits += 1
                return route

        route = self._reroute(
            source_id
        )

        self.route_table[
            source_id
        ] = route

        return route

    def get_metrics(self):

        if self.route_requests > 0:

            hit_ratio = (
                self.route_table_hits
                /
                self.route_requests
            )

        else:

            hit_ratio = 0.0

        return {
            "routing_requests":
                self.route_requests,

            "route_table_hits":
                self.route_table_hits,

            "route_table_builds":
                self.route_table_builds,

            "routing_reroutes":
                self.on_demand_reroutes,

            "route_cache_hit_ratio":
                hit_ratio
        }