from math import inf
from typing import Dict

import networkx as nx

from core.sensor import SensorNode
from routing.minimum_hop import (
    RouteResult,
    calculate_route_distance
)
from routing.ecmhr import ECMHRRouteResult


def build_minimum_hop_route_table(
    graph: nx.Graph,
    sensor_ids: list[int],
    sink_id="SINK"
) -> dict[int, RouteResult | None]:
    """
    Build minimum-hop routes for all sensors
    using ONE BFS rooted at the Sink.
    """

    routes = {
        sensor_id: None
        for sensor_id in sensor_ids
    }

    if sink_id not in graph:
        return routes

    # One BFS from Sink.
    sink_paths = (
        nx.single_source_shortest_path(
            graph,
            sink_id
        )
    )

    for sensor_id in sensor_ids:

        if sensor_id not in sink_paths:
            continue

        # NetworkX gives:
        # Sink -> ... -> Sensor
        #
        # We need:
        # Sensor -> ... -> Sink
        path = list(
            reversed(
                sink_paths[sensor_id]
            )
        )

        routes[sensor_id] = RouteResult(
            path=path,
            hop_count=len(path) - 1,
            total_distance_m=(
                calculate_route_distance(
                    graph,
                    path
                )
            )
        )

    return routes

def _build_ecmhr_table_for_threshold(
    graph: nx.Graph,
    sensor_map: Dict[int, SensorNode],
    sink_id,
    threshold_ratio: float,
    emergency_mode: bool
) -> dict[int, ECMHRRouteResult | None]:
    """
    Build ECMHR route table for all sensors
    for a fixed energy snapshot.

    Priority:
    1. Minimum hop
    2. Maximum bottleneck residual energy
    3. Minimum physical distance as final tie break
    """

    sensor_ids = list(
        sensor_map.keys()
    )

    routes = {
        sensor_id: None
        for sensor_id in sensor_ids
    }

    # Nodes allowed to act as relays.
    eligible_relays = {
        sensor.node_id
        for sensor in sensor_map.values()
        if (
            sensor.is_alive()
            and
            sensor.energy_ratio()
            > threshold_ratio
        )
    }

    relay_nodes = (
        eligible_relays
        |
        {sink_id}
    )

    relay_graph = graph.subgraph(
        relay_nodes
    ).copy()

    if sink_id not in relay_graph:
        return routes

    # Shortest hop distance from every
    # eligible relay to Sink.
    hop_distance = (
        nx.single_source_shortest_path_length(
            relay_graph,
            sink_id
        )
    )

    # next_hop[u] = best next relay toward Sink
    next_hop = {}

    # Internal value:
    # inf means the route contains no relay yet.
    best_bottleneck = {
        sink_id: inf
    }

    best_distance = {
        sink_id: 0.0
    }

    max_layer = max(
        hop_distance.values(),
        default=0
    )

    # -----------------------------------------
    # Build best route for eligible relay nodes
    # -----------------------------------------

    for layer in range(
        1,
        max_layer + 1
    ):

        layer_nodes = [
            node_id
            for node_id, distance
            in hop_distance.items()
            if distance == layer
        ]

        for node_id in layer_nodes:

            best_candidate = None
            best_candidate_bottleneck = -inf
            best_candidate_distance = inf

            for neighbor in relay_graph.neighbors(
                node_id
            ):

                if (
                    hop_distance.get(
                        neighbor
                    )
                    != layer - 1
                ):
                    continue

                # Bottleneck excludes SOURCE.
                # Therefore evaluate the next relay.
                if neighbor == sink_id:

                    candidate_bottleneck = inf

                else:

                    candidate_bottleneck = min(
                        sensor_map[
                            neighbor
                        ].remaining_energy,

                        best_bottleneck[
                            neighbor
                        ]
                    )

                candidate_distance = (
                    relay_graph[
                        node_id
                    ][
                        neighbor
                    ]["distance"]
                    +
                    best_distance[
                        neighbor
                    ]
                )

                if (
                    candidate_bottleneck
                    >
                    best_candidate_bottleneck
                ):

                    best_candidate = neighbor

                    best_candidate_bottleneck = (
                        candidate_bottleneck
                    )

                    best_candidate_distance = (
                        candidate_distance
                    )

                elif (
                    candidate_bottleneck
                    ==
                    best_candidate_bottleneck
                    and
                    candidate_distance
                    <
                    best_candidate_distance
                ):

                    best_candidate = neighbor

                    best_candidate_distance = (
                        candidate_distance
                    )

            if best_candidate is None:
                continue

            next_hop[
                node_id
            ] = best_candidate

            best_bottleneck[
                node_id
            ] = (
                best_candidate_bottleneck
            )

            best_distance[
                node_id
            ] = (
                best_candidate_distance
            )

    def reconstruct_relay_path(
        source_id
    ):

        if source_id == sink_id:
            return [sink_id]

        if source_id not in next_hop:
            return None

        path = [
            source_id
        ]

        current = source_id

        while current != sink_id:

            if current not in next_hop:
                return None

            current = next_hop[
                current
            ]

            path.append(
                current
            )

        return path

    # -----------------------------------------
    # Eligible sources
    # -----------------------------------------

    for source_id in sensor_ids:

        sensor = sensor_map[
            source_id
        ]

        if not sensor.is_alive():
            continue

        # Source itself is an eligible relay.
        if source_id in eligible_relays:

            if source_id not in hop_distance:
                continue

            path = reconstruct_relay_path(
                source_id
            )

            if path is None:
                continue

            bottleneck = (
                best_bottleneck[
                    source_id
                ]
            )

            if bottleneck == inf:
                bottleneck = None

            routes[source_id] = (
                ECMHRRouteResult(
                    path=path,

                    hop_count=(
                        len(path) - 1
                    ),

                    total_distance_m=(
                        best_distance[
                            source_id
                        ]
                    ),

                    bottleneck_energy_j=(
                        bottleneck
                    ),

                    emergency_mode=(
                        emergency_mode
                    ),

                    threshold_ratio_used=(
                        threshold_ratio
                    )
                )
            )

            continue

        # -------------------------------------
        # LOW_ENERGY source
        #
        # It may send its own packet,
        # but may NOT relay other packets.
        # -------------------------------------

        best_path = None

        best_hops = inf
        best_source_bottleneck = -inf
        best_source_distance = inf

        for neighbor in graph.neighbors(
            source_id
        ):

            # Direct to Sink
            if neighbor == sink_id:

                candidate_path = [
                    source_id,
                    sink_id
                ]

                candidate_hops = 1

                candidate_bottleneck = inf

                candidate_distance = (
                    graph[
                        source_id
                    ][
                        sink_id
                    ]["distance"]
                )

            else:

                if (
                    neighbor
                    not in eligible_relays
                ):
                    continue

                if (
                    neighbor
                    not in hop_distance
                ):
                    continue

                relay_path = (
                    reconstruct_relay_path(
                        neighbor
                    )
                )

                if relay_path is None:
                    continue

                candidate_path = (
                    [source_id]
                    +
                    relay_path
                )

                candidate_hops = (
                    len(candidate_path)
                    - 1
                )

                candidate_bottleneck = min(
                    sensor_map[
                        neighbor
                    ].remaining_energy,

                    best_bottleneck[
                        neighbor
                    ]
                )

                candidate_distance = (
                    graph[
                        source_id
                    ][
                        neighbor
                    ]["distance"]
                    +
                    best_distance[
                        neighbor
                    ]
                )

            if (
                candidate_hops
                <
                best_hops
            ):

                choose = True

            elif (
                candidate_hops
                ==
                best_hops
                and
                candidate_bottleneck
                >
                best_source_bottleneck
            ):

                choose = True

            elif (
                candidate_hops
                ==
                best_hops
                and
                candidate_bottleneck
                ==
                best_source_bottleneck
                and
                candidate_distance
                <
                best_source_distance
            ):

                choose = True

            else:
                choose = False

            if choose:

                best_path = candidate_path

                best_hops = (
                    candidate_hops
                )

                best_source_bottleneck = (
                    candidate_bottleneck
                )

                best_source_distance = (
                    candidate_distance
                )

        if best_path is None:
            continue

        bottleneck = (
            best_source_bottleneck
        )

        if bottleneck == inf:
            bottleneck = None

        routes[source_id] = (
            ECMHRRouteResult(
                path=best_path,

                hop_count=(
                    len(best_path) - 1
                ),

                total_distance_m=(
                    best_source_distance
                ),

                bottleneck_energy_j=(
                    bottleneck
                ),

                emergency_mode=(
                    emergency_mode
                ),

                threshold_ratio_used=(
                    threshold_ratio
                )
            )
        )

    return routes

def build_ecmhr_route_table(
    graph: nx.Graph,
    sensor_map: Dict[int, SensorNode],
    sink_id="SINK",
    energy_threshold_ratio: float = 0.20,
    allow_emergency_mode: bool = False,
    emergency_threshold_ratio: float = 0.10
) -> dict[int, ECMHRRouteResult | None]:

    normal_routes = (
        _build_ecmhr_table_for_threshold(
            graph=graph,

            sensor_map=sensor_map,

            sink_id=sink_id,

            threshold_ratio=(
                energy_threshold_ratio
            ),

            emergency_mode=False
        )
    )

    if not allow_emergency_mode:
        return normal_routes

    emergency_routes = (
        _build_ecmhr_table_for_threshold(
            graph=graph,

            sensor_map=sensor_map,

            sink_id=sink_id,

            threshold_ratio=(
                emergency_threshold_ratio
            ),

            emergency_mode=True
        )
    )

    final_routes = {}

    for source_id in sensor_map:

        normal = normal_routes.get(
            source_id
        )

        if normal is not None:

            final_routes[
                source_id
            ] = normal

        else:

            final_routes[
                source_id
            ] = emergency_routes.get(
                source_id
            )

    return final_routes