import unittest

import networkx as nx
from pathlib import Path

import yaml

from core.network import WirelessSensorNetwork
from topology.deployment import (
    create_sink,
    deploy_sensors
)
from routing.minimum_hop import (
    calculate_route_distance,
    find_minimum_hop_route
)


class MinimumHopRoutingTest(unittest.TestCase):

    def test_direct_route(self):

        graph = nx.Graph()

        graph.add_edge(
            1,
            "SINK",
            distance=100.0
        )

        route = find_minimum_hop_route(
            graph,
            1,
            "SINK"
        )

        self.assertIsNotNone(route)

        self.assertEqual(
            route.path,
            [1, "SINK"]
        )

        self.assertEqual(
            route.hop_count,
            1
        )

    def test_minimum_hop_route(self):

        graph = nx.Graph()

        # Route A: 2 hops
        graph.add_edge(
            1,
            2,
            distance=100
        )

        graph.add_edge(
            2,
            "SINK",
            distance=100
        )

        # Route B: 3 hops
        graph.add_edge(
            1,
            3,
            distance=50
        )

        graph.add_edge(
            3,
            4,
            distance=50
        )

        graph.add_edge(
            4,
            "SINK",
            distance=50
        )

        route = find_minimum_hop_route(
            graph,
            1
        )

        self.assertEqual(
            route.hop_count,
            2
        )

        self.assertEqual(
            route.path,
            [1, 2, "SINK"]
        )

    def test_minimum_hop_not_minimum_distance(self):

        graph = nx.Graph()

        # 2 hops, but physically longer
        graph.add_edge(
            1,
            2,
            distance=190
        )

        graph.add_edge(
            2,
            "SINK",
            distance=190
        )

        # 3 hops, but physically shorter
        graph.add_edge(
            1,
            3,
            distance=50
        )

        graph.add_edge(
            3,
            4,
            distance=50
        )

        graph.add_edge(
            4,
            "SINK",
            distance=50
        )

        route = find_minimum_hop_route(
            graph,
            1
        )

        self.assertEqual(
            route.path,
            [1, 2, "SINK"]
        )

        self.assertEqual(
            route.hop_count,
            2
        )

    def test_disconnected_sensor(self):

        graph = nx.Graph()

        graph.add_node(1)

        graph.add_node("SINK")

        route = find_minimum_hop_route(
            graph,
            1
        )

        self.assertIsNone(route)

    def test_invalid_source(self):

        graph = nx.Graph()

        graph.add_node("SINK")

        with self.assertRaises(
            ValueError
        ):

            find_minimum_hop_route(
                graph,
                999
            )

    def test_route_distance(self):

        graph = nx.Graph()

        graph.add_edge(
            1,
            2,
            distance=100
        )

        graph.add_edge(
            2,
            3,
            distance=150
        )

        distance = calculate_route_distance(
            graph,
            [1, 2, 3]
        )

        self.assertEqual(
            distance,
            250
        )

class FullNetworkRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        config_path = (
            Path(__file__).parent.parent
            / "config.yaml"
        )

        with open(
            config_path,
            "r",
            encoding="utf-8"
        ) as file:

            cls.config = yaml.safe_load(
                file
            )

        cls.sensors = deploy_sensors(
            cls.config
        )

        cls.sink = create_sink(
            cls.config
        )

        cls.network = WirelessSensorNetwork(
            sensors=cls.sensors,
            sink=cls.sink
        )

        cls.network.build_topology()

    def test_all_routes_have_valid_edges(self):

        routes = (
            self.network
            .find_all_minimum_hop_routes()
        )

        for route in routes.values():

            if route is None:
                continue

            for index in range(
                len(route.path) - 1
            ):

                node_a = route.path[index]

                node_b = route.path[
                    index + 1
                ]

                self.assertTrue(
                    self.network.graph.has_edge(
                        node_a,
                        node_b
                    )
                )

    def test_routes_end_at_sink(self):

        routes = (
            self.network
            .find_all_minimum_hop_routes()
        )

        for route in routes.values():

            if route is None:
                continue

            self.assertEqual(
                route.path[-1],
                self.sink.node_id
            )

    def test_hop_count_matches_path(self):

        routes = (
            self.network
            .find_all_minimum_hop_routes()
        )

        for route in routes.values():

            if route is None:
                continue

            self.assertEqual(
                route.hop_count,
                len(route.path) - 1
            )

if __name__ == "__main__":
    unittest.main()