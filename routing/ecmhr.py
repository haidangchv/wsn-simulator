from dataclasses import dataclass
from math import inf, isclose
from typing import Dict, Union

import networkx as nx

from core.sensor import SensorNode
from routing.minimum_hop import (
    calculate_route_distance
)


NodeId = Union[int, str]


@dataclass
class ECMHRRouteResult:
    path: list[NodeId]

    hop_count: int

    total_distance_m: float

    bottleneck_energy_j: float | None

    emergency_mode: bool = False

    threshold_ratio_used: float = 0.20

    def __repr__(self) -> str:

        path_text = " -> ".join(
            str(node)
            for node in self.path
        )

        bottleneck = (
            f"{self.bottleneck_energy_j:.4f} J"
            if self.bottleneck_energy_j is not None
            else "N/A"
        )

        return (
            "ECMHRRouteResult("
            f"path={path_text}, "
            f"hops={self.hop_count}, "
            f"distance={self.total_distance_m:.2f}m, "
            f"bottleneck={bottleneck}, "
            f"emergency={self.emergency_mode}"
            ")"
        )


def _build_eligible_graph(
    graph: nx.Graph,
    sensor_map: Dict[int, SensorNode],
    source_id: int,
    sink_id: NodeId,
    threshold_ratio: float
) -> nx.Graph:
    """
    Create a graph containing only eligible relay nodes.

    Rules:
    - Sink is always available.
    - Source may send its own data while LOW_ENERGY.
    - DEAD source cannot send.
    - Relay nodes must be alive and above threshold.
    """

    eligible_graph = graph.copy()

    if source_id not in sensor_map:
        return nx.Graph()

    source = sensor_map[source_id]

    if not source.is_alive():
        return nx.Graph()

    nodes_to_remove = []

    for node_id in eligible_graph.nodes:

        if node_id == sink_id:
            continue

        if node_id == source_id:
            continue

        sensor = sensor_map.get(node_id)

        if sensor is None:
            continue

        if not sensor.is_alive():

            nodes_to_remove.append(
                node_id
            )

            continue

        if (
            sensor.energy_ratio()
            <= threshold_ratio
        ):

            nodes_to_remove.append(
                node_id
            )

    eligible_graph.remove_nodes_from(
        nodes_to_remove
    )

    return eligible_graph


def _find_best_shortest_path(
    graph: nx.Graph,
    sensor_map: Dict[int, SensorNode],
    source_id: int,
    sink_id: NodeId,
    threshold_ratio: float,
    emergency_mode: bool
) -> ECMHRRouteResult | None:
    """
    Among all shortest-hop paths, select the
    path whose minimum relay residual energy
    is the greatest.

    If bottleneck energies are equal, prefer
    smaller physical distance for deterministic
    tie breaking.
    """

    if (
        source_id not in graph
        or sink_id not in graph
    ):
        return None

    distance_from_source = (
        nx.single_source_shortest_path_length(
            graph,
            source_id
        )
    )

    if sink_id not in distance_from_source:
        return None

    distance_to_sink = (
        nx.single_source_shortest_path_length(
            graph,
            sink_id
        )
    )

    minimum_hops = (
        distance_from_source[
            sink_id
        ]
    )

    best_bottleneck = {
        source_id: inf
    }

    best_distance = {
        source_id: 0.0
    }

    predecessor: Dict[
        NodeId,
        NodeId
    ] = {}

    for layer in range(
        minimum_hops
    ):

        layer_nodes = [
            node
            for node, hop_distance
            in distance_from_source.items()
            if hop_distance == layer
        ]

        for current in layer_nodes:

            if current not in best_bottleneck:
                continue

            if current not in distance_to_sink:
                continue

            # Current node must belong to at least
            # one minimum-hop path.
            if (
                distance_from_source[current]
                +
                distance_to_sink[current]
                != minimum_hops
            ):
                continue

            for neighbor in graph.neighbors(
                current
            ):

                if (
                    distance_from_source.get(
                        neighbor
                    )
                    != layer + 1
                ):
                    continue

                if neighbor not in distance_to_sink:
                    continue

                # Neighbor must also lie on a
                # minimum-hop path.
                if (
                    distance_from_source[
                        neighbor
                    ]
                    +
                    distance_to_sink[
                        neighbor
                    ]
                    != minimum_hops
                ):
                    continue

                candidate_bottleneck = (
                    best_bottleneck[
                        current
                    ]
                )

                # Source and sink are excluded from
                # relay bottleneck calculation.
                if neighbor != sink_id:

                    relay_energy = (
                        sensor_map[
                            neighbor
                        ].remaining_energy
                    )

                    candidate_bottleneck = min(
                        candidate_bottleneck,
                        relay_energy
                    )

                edge_distance = (
                    graph[
                        current
                    ][
                        neighbor
                    ]["distance"]
                )

                candidate_distance = (
                    best_distance[
                        current
                    ]
                    +
                    edge_distance
                )

                current_best = (
                    best_bottleneck.get(
                        neighbor,
                        -inf
                    )
                )

                current_best_distance = (
                    best_distance.get(
                        neighbor,
                        inf
                    )
                )

                better_energy = (
                    candidate_bottleneck
                    >
                    current_best
                )

                equal_energy = (
                    isclose(
                        candidate_bottleneck,
                        current_best,
                        rel_tol=1e-12,
                        abs_tol=1e-12
                    )
                )

                better_distance = (
                    candidate_distance
                    <
                    current_best_distance
                )

                if (
                    better_energy
                    or
                    (
                        equal_energy
                        and better_distance
                    )
                ):

                    best_bottleneck[
                        neighbor
                    ] = candidate_bottleneck

                    best_distance[
                        neighbor
                    ] = candidate_distance

                    predecessor[
                        neighbor
                    ] = current

    if sink_id not in predecessor:
        return None

    path = [
        sink_id
    ]

    current = sink_id

    while current != source_id:

        current = predecessor[
            current
        ]

        path.append(
            current
        )

    path.reverse()

    total_distance = (
        calculate_route_distance(
            graph,
            path
        )
    )

    bottleneck = (
        best_bottleneck[
            sink_id
        ]
    )

    # Direct Source -> Sink contains no relay.
    if bottleneck == inf:
        bottleneck = None

    return ECMHRRouteResult(
        path=path,

        hop_count=(
            len(path) - 1
        ),

        total_distance_m=(
            total_distance
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


def find_ecmhr_route(
    graph: nx.Graph,
    sensor_map: Dict[int, SensorNode],
    source_id: int,
    sink_id: NodeId = "SINK",
    energy_threshold_ratio: float = 0.20,
    allow_emergency_mode: bool = False,
    emergency_threshold_ratio: float = 0.10
) -> ECMHRRouteResult | None:
    """
    Energy-Constrained Minimum-Hop Routing.

    Priority:
    1. Exclude low-energy/dead relays.
    2. Minimize hop count.
    3. Maximize minimum relay energy.
    """

    normal_graph = (
        _build_eligible_graph(
            graph=graph,
            sensor_map=sensor_map,
            source_id=source_id,
            sink_id=sink_id,
            threshold_ratio=(
                energy_threshold_ratio
            )
        )
    )

    result = (
        _find_best_shortest_path(
            graph=normal_graph,
            sensor_map=sensor_map,
            source_id=source_id,
            sink_id=sink_id,
            threshold_ratio=(
                energy_threshold_ratio
            ),
            emergency_mode=False
        )
    )

    if result is not None:
        return result

    if not allow_emergency_mode:
        return None

    if (
        emergency_threshold_ratio
        >= energy_threshold_ratio
    ):

        raise ValueError(
            "Emergency threshold must be "
            "lower than normal threshold."
        )

    emergency_graph = (
        _build_eligible_graph(
            graph=graph,
            sensor_map=sensor_map,
            source_id=source_id,
            sink_id=sink_id,
            threshold_ratio=(
                emergency_threshold_ratio
            )
        )
    )

    return _find_best_shortest_path(
        graph=emergency_graph,
        sensor_map=sensor_map,
        source_id=source_id,
        sink_id=sink_id,
        threshold_ratio=(
            emergency_threshold_ratio
        ),
        emergency_mode=True
    )