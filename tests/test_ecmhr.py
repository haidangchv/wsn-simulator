import unittest

import networkx as nx

from core.sensor import SensorNode
from routing.ecmhr import (
    find_ecmhr_route
)


def create_sensor(
    node_id,
    energy
):

    return SensorNode(
        node_id=node_id,
        x=0,
        y=0,
        sensor_type="temperature",
        initial_energy=2.0,
        remaining_energy=energy,
        transmission_range=200
    )


class ECMHRTest(
    unittest.TestCase
):

    def test_low_energy_relay_is_avoided(
        self
    ):

        graph = nx.Graph()

        # Short route but relay 2 is LOW_ENERGY
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

        # Alternative valid route
        graph.add_edge(
            1,
            3,
            distance=100
        )

        graph.add_edge(
            3,
            4,
            distance=100
        )

        graph.add_edge(
            4,
            "SINK",
            distance=100
        )

        sensor_map = {
            1: create_sensor(1, 2.0),
            2: create_sensor(2, 0.30),
            3: create_sensor(3, 1.50),
            4: create_sensor(4, 1.50)
        }

        route = find_ecmhr_route(
            graph=graph,
            sensor_map=sensor_map,
            source_id=1,
            energy_threshold_ratio=0.20
        )

        self.assertIsNotNone(
            route
        )

        self.assertEqual(
            route.path,
            [1, 3, 4, "SINK"]
        )

    def test_same_hop_prefers_higher_bottleneck(
        self
    ):

        graph = nx.Graph()

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

        graph.add_edge(
            1,
            3,
            distance=100
        )

        graph.add_edge(
            3,
            "SINK",
            distance=100
        )

        sensor_map = {
            1: create_sensor(1, 2.0),

            2: create_sensor(
                2,
                0.80
            ),

            3: create_sensor(
                3,
                1.50
            )
        }

        route = find_ecmhr_route(
            graph=graph,
            sensor_map=sensor_map,
            source_id=1
        )

        self.assertEqual(
            route.path,
            [1, 3, "SINK"]
        )

        self.assertAlmostEqual(
            route.bottleneck_energy_j,
            1.50
        )

    def test_low_energy_source_can_send(
        self
    ):

        graph = nx.Graph()

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

        sensor_map = {
            1: create_sensor(
                1,
                0.30
            ),

            2: create_sensor(
                2,
                1.50
            )
        }

        route = find_ecmhr_route(
            graph=graph,
            sensor_map=sensor_map,
            source_id=1
        )

        self.assertIsNotNone(
            route
        )

        self.assertEqual(
            route.path,
            [1, 2, "SINK"]
        )

    def test_no_valid_route(
        self
    ):

        graph = nx.Graph()

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

        sensor_map = {
            1: create_sensor(
                1,
                2.0
            ),

            2: create_sensor(
                2,
                0.30
            )
        }

        route = find_ecmhr_route(
            graph=graph,
            sensor_map=sensor_map,
            source_id=1,
            energy_threshold_ratio=0.20
        )

        self.assertIsNone(
            route
        )

    def test_emergency_mode(
        self
    ):

        graph = nx.Graph()

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

        sensor_map = {
            1: create_sensor(
                1,
                2.0
            ),

            # 15% energy.
            # Invalid at 20%, valid at 10%.
            2: create_sensor(
                2,
                0.30
            )
        }

        route = find_ecmhr_route(
            graph=graph,
            sensor_map=sensor_map,
            source_id=1,
            energy_threshold_ratio=0.20,
            allow_emergency_mode=True,
            emergency_threshold_ratio=0.10
        )

        self.assertIsNotNone(
            route
        )

        self.assertTrue(
            route.emergency_mode
        )

        self.assertEqual(
            route.path,
            [1, 2, "SINK"]
        )


if __name__ == "__main__":
    unittest.main()