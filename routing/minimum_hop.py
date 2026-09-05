from collections import deque
from dataclasses import dataclass
from typing import Dict, Optional, Union

import networkx as nx


NodeId = Union[int, str]


@dataclass
class RouteResult:
    path: list[NodeId]
    hop_count: int
    total_distance_m: float

    def __repr__(self) -> str:
        path_text = " -> ".join(
            str(node)
            for node in self.path
        )

        return (
            f"RouteResult("
            f"path={path_text}, "
            f"hops={self.hop_count}, "
            f"distance={self.total_distance_m:.2f}m"
            f")"
        )


def calculate_route_distance(
    graph: nx.Graph,
    path: list[NodeId]
) -> float:
    """
    Calculate total physical distance of a route.
    """

    total_distance = 0.0

    for i in range(len(path) - 1):

        node_a = path[i]
        node_b = path[i + 1]

        edge_data = graph.get_edge_data(
            node_a,
            node_b
        )

        if edge_data is None:
            raise ValueError(
                f"No edge between "
                f"{node_a} and {node_b}."
            )

        total_distance += edge_data["distance"]

    return total_distance


def find_minimum_hop_route(
    graph: nx.Graph,
    source_id: NodeId,
    sink_id: NodeId = "SINK"
) -> Optional[RouteResult]:
    """
    Find the minimum-hop route from source
    sensor to sink using Breadth-First Search.

    Returns None when no route exists.
    """

    if source_id not in graph:
        raise ValueError(
            f"Source node {source_id} "
            f"does not exist in graph."
        )

    if sink_id not in graph:
        raise ValueError(
            f"Sink node {sink_id} "
            f"does not exist in graph."
        )

    if source_id == sink_id:
        return RouteResult(
            path=[sink_id],
            hop_count=0,
            total_distance_m=0.0
        )

    queue = deque([source_id])

    predecessor: Dict[NodeId, Optional[NodeId]] = {
        source_id: None
    }

    found = False

    while queue:

        current = queue.popleft()

        if current == sink_id:
            found = True
            break

        for neighbor in graph.neighbors(current):

            if neighbor in predecessor:
                continue

            predecessor[neighbor] = current

            queue.append(neighbor)

            if neighbor == sink_id:
                found = True
                queue.clear()
                break

    if not found:
        return None

    path = []

    current: Optional[NodeId] = sink_id

    while current is not None:

        path.append(current)

        current = predecessor[current]

    path.reverse()

    hop_count = len(path) - 1

    total_distance = calculate_route_distance(
        graph,
        path
    )

    return RouteResult(
        path=path,
        hop_count=hop_count,
        total_distance_m=total_distance
    )

def find_all_minimum_hop_routes(
graph: nx.Graph,
sensor_ids: list[int],
sink_id: NodeId = "SINK"
) -> dict[int, Optional[RouteResult]]:
    """
    Calculate minimum-hop routes for all sensors.
    """

    routes = {}

    for sensor_id in sensor_ids:

        routes[sensor_id] = (
            find_minimum_hop_route(
                graph=graph,
                source_id=sensor_id,
                sink_id=sink_id
            )
        )

    return routes

def calculate_route_statistics(
routes: dict[int, Optional[RouteResult]]
) -> dict:
    """
    Calculate routing statistics.
    """

    valid_routes = [
        route
        for route in routes.values()
        if route is not None
    ]

    total_sensors = len(routes)

    routable = len(valid_routes)

    unroutable = (
        total_sensors - routable
    )

    if not valid_routes:

        return {
            "total_sensors": total_sensors,
            "routable_sensors": 0,
            "unroutable_sensors": unroutable,
            "minimum_hops": None,
            "maximum_hops": None,
            "average_hops": None,
            "average_distance_m": None
        }

    hop_counts = [
        route.hop_count
        for route in valid_routes
    ]

    distances = [
        route.total_distance_m
        for route in valid_routes
    ]

    return {
        "total_sensors": total_sensors,

        "routable_sensors":
            routable,

        "unroutable_sensors":
            unroutable,

        "minimum_hops":
            min(hop_counts),

        "maximum_hops":
            max(hop_counts),

        "average_hops":
            sum(hop_counts)
            / len(hop_counts),

        "average_distance_m":
            sum(distances)
            / len(distances)
    }