import unittest
from pathlib import Path

import yaml

from core.network import WirelessSensorNetwork
from topology.deployment import (
    create_sink,
    deploy_sensors
)
from topology.neighbor_graph import (
    calculate_distance
)


def load_config():

    config_path = (
        Path(__file__).parent.parent
        / "config.yaml"
    )

    with open(
        config_path,
        "r",
        encoding="utf-8"
    ) as file:

        return yaml.safe_load(file)


class NeighborGraphTest(unittest.TestCase):

    def setUp(self):

        self.config = load_config()

        self.sensors = deploy_sensors(
            self.config
        )

        self.sink = create_sink(
            self.config
        )

        self.network = WirelessSensorNetwork(
            sensors=self.sensors,
            sink=self.sink
        )

        self.network.build_topology()

    def test_graph_node_count(self):

        self.assertEqual(
            self.network.graph.number_of_nodes(),
            501
        )

    def test_graph_has_edges(self):

        self.assertGreater(
            self.network.graph.number_of_edges(),
            0
        )

    def test_no_self_loops(self):

        for node_a, node_b in (
            self.network.graph.edges()
        ):

            self.assertNotEqual(
                node_a,
                node_b
            )

    def test_sensor_links_within_range(self):

        sensor_map = {
            sensor.node_id: sensor
            for sensor in self.sensors
        }

        for node_a, node_b in (
            self.network.graph.edges()
        ):

            # Skip sensor-to-sink test here
            if (
                node_a == self.sink.node_id
                or
                node_b == self.sink.node_id
            ):
                continue

            sensor_a = sensor_map[node_a]

            sensor_b = sensor_map[node_b]

            distance = calculate_distance(
                sensor_a.x,
                sensor_a.y,
                sensor_b.x,
                sensor_b.y
            )

            max_range = min(
                sensor_a.transmission_range,
                sensor_b.transmission_range
            )

            self.assertLessEqual(
                distance,
                max_range
            )

    def test_sink_links_within_range(self):

        sensor_map = {
            sensor.node_id: sensor
            for sensor in self.sensors
        }

        for node_id in (
            self.network.direct_sink_neighbors()
        ):

            sensor = sensor_map[node_id]

            distance = calculate_distance(
                sensor.x,
                sensor.y,
                self.sink.x,
                self.sink.y
            )

            self.assertLessEqual(
                distance,
                sensor.transmission_range
            )

    def test_neighbor_lists_match_graph(self):

        for sensor in self.sensors:

            graph_neighbors = {
                node
                for node in self.network.graph.neighbors(
                    sensor.node_id
                )
                if node != self.sink.node_id
            }

            stored_neighbors = set(
                sensor.neighbors
            )

            self.assertEqual(
                graph_neighbors,
                stored_neighbors
            )


if __name__ == "__main__":
    unittest.main()