import math
from typing import List

import networkx as nx

from core.sensor import SensorNode
from core.sink import SinkNode


def calculate_distance(
    x1: float,
    y1: float,
    x2: float,
    y2: float
) -> float:
    """
    Euclidean distance between two points.
    """

    return math.sqrt(
        (x1 - x2) ** 2
        +
        (y1 - y2) ** 2
    )


def build_neighbor_graph(
    sensors: List[SensorNode],
    sink: SinkNode
) -> nx.Graph:
    """
    Build an undirected graph for the wireless
    sensor network.

    Two sensor nodes are connected when their
    distance is within transmission range.

    A sensor is connected directly to the sink
    when the sink is within its transmission range.
    """

    graph = nx.Graph()

    # Reset neighbor information
    for sensor in sensors:
        sensor.neighbors.clear()

    # Add sensor nodes
    for sensor in sensors:

        graph.add_node(
            sensor.node_id,
            node_type="sensor",
            x=sensor.x,
            y=sensor.y,
            sensor_type=sensor.sensor_type,
            energy=sensor.remaining_energy
        )

    # Add sink node
    graph.add_node(
        sink.node_id,
        node_type="sink",
        x=sink.x,
        y=sink.y
    )

    # Build sensor-to-sensor links
    for i in range(len(sensors)):

        sensor_i = sensors[i]

        for j in range(i + 1, len(sensors)):

            sensor_j = sensors[j]

            distance = calculate_distance(
                sensor_i.x,
                sensor_i.y,
                sensor_j.x,
                sensor_j.y
            )

            # Both nodes must be able to communicate
            transmission_range = min(
                sensor_i.transmission_range,
                sensor_j.transmission_range
            )

            if distance <= transmission_range:

                graph.add_edge(
                    sensor_i.node_id,
                    sensor_j.node_id,
                    distance=distance
                )

                sensor_i.neighbors.append(
                    sensor_j.node_id
                )

                sensor_j.neighbors.append(
                    sensor_i.node_id
                )

    # Build sensor-to-sink links
    for sensor in sensors:

        distance_to_sink = calculate_distance(
            sensor.x,
            sensor.y,
            sink.x,
            sink.y
        )

        if distance_to_sink <= sensor.transmission_range:

            graph.add_edge(
                sensor.node_id,
                sink.node_id,
                distance=distance_to_sink
            )

    return graph