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
            )
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

    def prepare_round(self):
        """
        Build all routes using the current
        energy/load snapshot.
        """

        if (
            self.algorithm
            == "minimum_hop"
        ):

            self._build_minimum_hop_table()
            return

        if (
            self.algorithm
            == "lb_ecmhr"
        ):

            # Load reflects preceding rounds
            self.load_tracker.update(
                self.network.sensors
            )

            self.route_table = (
                self.lb_ecmhr_router
                .build_route_table(
                    load_factors=(
                        self.load_tracker
                        .load_factors
                    ),
                    overloaded_nodes=(
                        self.load_tracker
                        .overloaded_nodes
                    )
                )
            )

            self.route_table_builds += 1
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

        self.route_table = (
            self.lb_ecmhr_router.build_route_table(
                load_factors=(
                    self.load_tracker.load_factors
                ),
                overloaded_nodes=(
                    self.load_tracker.overloaded_nodes
                )
            )
        )
        return self.route_table.get(
            source_id
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