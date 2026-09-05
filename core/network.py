from dataclasses import dataclass, field
from typing import List

import networkx as nx
from routing.minimum_hop import (
    RouteResult,
    calculate_route_statistics,
    find_all_minimum_hop_routes,
    find_minimum_hop_route
)
from core.sensor import SensorNode
from core.sink import SinkNode
from topology.neighbor_graph import build_neighbor_graph


@dataclass
class WirelessSensorNetwork:
    sensors: List[SensorNode]
    sink: SinkNode

    graph: nx.Graph = field(
        default_factory=nx.Graph
    )

    def find_minimum_hop_route(
        self,
        source_id: int
    ) -> RouteResult | None:
        """
        Find minimum-hop route from a
        sensor node to sink.
        """

        return find_minimum_hop_route(
            graph=self.graph,
            source_id=source_id,
            sink_id=self.sink.node_id
        )

    def find_all_minimum_hop_routes(self):
        """
        Find routes from all sensors to sink.
        """
        sensor_ids = [
            sensor.node_id
            for sensor in self.sensors
        ]

        return find_all_minimum_hop_routes(
            graph=self.graph,
            sensor_ids=sensor_ids,
            sink_id=self.sink.node_id
        )

    def minimum_hop_statistics(self) -> dict:
        """
        Return global minimum-hop statistics.
        """

        routes = (
            self.find_all_minimum_hop_routes()
        )

        return calculate_route_statistics(
            routes
        )

    def build_topology(self) -> None:
        """
        Build wireless communication topology.
        """

        self.graph = build_neighbor_graph(
            sensors=self.sensors,
            sink=self.sink
        )

    def get_sensor(self, node_id: int) -> SensorNode:
        """
        Return sensor by ID.
        """

        for sensor in self.sensors:

            if sensor.node_id == node_id:
                return sensor

        raise ValueError(
            f"Sensor {node_id} not found."
        )

    def connected_sensor_ids(self) -> set:
        """
        Return IDs of sensor nodes that have
        at least one path to the sink.
        """

        if self.sink.node_id not in self.graph:
            return set()

        component = nx.node_connected_component(
            self.graph,
            self.sink.node_id
        )

        return {
            node_id
            for node_id in component
            if node_id != self.sink.node_id
        }

    def isolated_sensor_ids(self) -> List[int]:
        """
        Return sensors with no communication link.
        """

        return [
            sensor.node_id
            for sensor in self.sensors
            if self.graph.degree(sensor.node_id) == 0
        ]

    def direct_sink_neighbors(self) -> List[int]:
        """
        Return sensors that can communicate
        directly with sink.
        """

        return [
            node_id
            for node_id in self.graph.neighbors(
                self.sink.node_id
            )
            if node_id != self.sink.node_id
        ]

    def average_sensor_degree(self) -> float:
        """
        Average number of communication links
        per sensor.
        """

        if not self.sensors:
            return 0.0

        total_degree = sum(
            self.graph.degree(sensor.node_id)
            for sensor in self.sensors
        )

        return total_degree / len(self.sensors)

    def connectivity_ratio(self) -> float:
        """
        Percentage of sensors having a path
        to sink.
        """

        if not self.sensors:
            return 0.0

        connected = len(
            self.connected_sensor_ids()
        )

        return connected / len(self.sensors)

    
    def get_statistics(self) -> dict:
        """
        Return main topology statistics.
        """

        connected = self.connected_sensor_ids()

        isolated = self.isolated_sensor_ids()

        direct_sink = self.direct_sink_neighbors()

        return {
            "num_sensors": len(self.sensors),

            "num_nodes_total":
                self.graph.number_of_nodes(),

            "num_edges":
                self.graph.number_of_edges(),

            "connected_to_sink":
                len(connected),

            "disconnected_from_sink":
                len(self.sensors) - len(connected),

            "isolated_sensors":
                len(isolated),

            "direct_sink_neighbors":
                len(direct_sink),

            "average_sensor_degree":
                self.average_sensor_degree(),

            "connectivity_ratio":
                self.connectivity_ratio()
        }

    