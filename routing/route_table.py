import networkx as nx

from routing.minimum_hop import (
    RouteResult,
    calculate_route_distance
)


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

    # One BFS from Sink
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