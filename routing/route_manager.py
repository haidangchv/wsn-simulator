from routing.ecmhr import (
    find_ecmhr_route
)

from routing.minimum_hop import (
    find_minimum_hop_route
)

from routing.route_table import (
    build_ecmhr_route_table,
    build_minimum_hop_route_table
)


class RouteManager:

    def __init__(
        self,
        network,
        config,
        algorithm="minimum_hop"
    ):

        self.network = network
        self.config = config

        self.algorithm = algorithm

        self.route_table = {}

        self.route_requests = 0

        self.route_table_hits = 0

        self.route_table_builds = 0

        self.on_demand_reroutes = 0

        self.sensor_map = {
            sensor.node_id: sensor
            for sensor in network.sensors
        }

        routing_config = (
            config.get(
                "routing",
                {}
            )
        )

        self.energy_threshold_ratio = (
            config["sensor"][
                "energy_threshold_ratio"
            ]
        )

        self.allow_emergency_mode = (
            routing_config.get(
                "allow_emergency_mode",
                False
            )
        )

        self.emergency_threshold_ratio = (
            routing_config.get(
                "emergency_threshold_ratio",
                0.10
            )
        )

    def set_algorithm(
        self,
        algorithm
    ):

        if algorithm not in {
            "minimum_hop",
            "ecmhr"
        }:

            raise ValueError(
                f"Unsupported routing algorithm: "
                f"{algorithm}"
            )

        self.algorithm = algorithm

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

    def prepare_round(self):
        """
        Build all routes using the current
        energy/network snapshot.
        """

        sensor_ids = [
            sensor.node_id
            for sensor
            in self.network.sensors
        ]

        if (
            self.algorithm
            == "minimum_hop"
        ):

            graph = (
                self._active_minimum_hop_graph()
            )

            self.route_table = (
                build_minimum_hop_route_table(
                    graph=graph,

                    sensor_ids=(
                        sensor_ids
                    ),

                    sink_id=(
                        self.network
                        .sink
                        .node_id
                    )
                )
            )

        elif (
            self.algorithm
            == "ecmhr"
        ):

            self.route_table = (
                build_ecmhr_route_table(
                    graph=(
                        self.network.graph
                    ),

                    sensor_map=(
                        self.sensor_map
                    ),

                    sink_id=(
                        self.network
                        .sink
                        .node_id
                    ),

                    energy_threshold_ratio=(
                        self.energy_threshold_ratio
                    ),

                    allow_emergency_mode=(
                        self.allow_emergency_mode
                    ),

                    emergency_threshold_ratio=(
                        self.emergency_threshold_ratio
                    )
                )
            )

        self.route_table_builds += 1

    def _route_is_valid(
        self,
        route
    ) -> bool:

        if route is None:
            return False

        if not route.path:
            return False

        source_id = (
            route.path[0]
        )

        if source_id not in self.sensor_map:
            return False

        source = self.sensor_map[
            source_id
        ]

        if not source.is_alive():
            return False

        # Intermediate nodes only.
        relay_ids = (
            route.path[1:-1]
        )

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
                == "ecmhr"
            ):

                threshold = getattr(
                    route,
                    "threshold_ratio_used",
                    self.energy_threshold_ratio
                )

                if (
                    relay.energy_ratio()
                    <= threshold
                ):

                    return False

        # Physical links must still exist.
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

        return find_ecmhr_route(
            graph=self.network.graph,

            sensor_map=self.sensor_map,

            source_id=source_id,

            sink_id=(
                self.network
                .sink
                .node_id
            ),

            energy_threshold_ratio=(
                self.energy_threshold_ratio
            ),

            allow_emergency_mode=(
                self.allow_emergency_mode
            ),

            emergency_threshold_ratio=(
                self.emergency_threshold_ratio
            )
        )

    def get_route(
        self,
        source_id
    ):

        self.route_requests += 1

        route = (
            self.route_table.get(
                source_id
            )
        )

        if self._route_is_valid(
            route
        ):

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