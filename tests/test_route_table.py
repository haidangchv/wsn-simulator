import unittest

import networkx as nx

from routing.minimum_hop import (
    find_minimum_hop_route
)

from routing.route_table import (
    build_minimum_hop_route_table
)

from core.sensor import SensorNode

from routing.ecmhr import (
    find_ecmhr_route
)

from routing.route_table import (
    build_ecmhr_route_table
)
def sensor(
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


class ECMHRRouteTableTest(
    unittest.TestCase
):

    def test_higher_energy_path_selected(
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
            1: sensor(
                1,
                2.0
            ),

            2: sensor(
                2,
                0.8
            ),

            3: sensor(
                3,
                1.5
            )
        }

        table = (
            build_ecmhr_route_table(
                graph=graph,

                sensor_map=(
                    sensor_map
                ),

                energy_threshold_ratio=(
                    0.20
                )
            )
        )

        route = table[1]

        self.assertEqual(
            route.path,
            [
                1,
                3,
                "SINK"
            ]
        )
    
class MinimumHopRouteTableTest(
    unittest.TestCase
):

    def setUp(self):

        self.graph = nx.Graph()

        self.graph.add_edge(
            1,
            2,
            distance=100
        )

        self.graph.add_edge(
            2,
            "SINK",
            distance=100
        )

        self.graph.add_edge(
            3,
            2,
            distance=50
        )

    def test_routes_exist(self):

        table = (
            build_minimum_hop_route_table(
                graph=self.graph,

                sensor_ids=[
                    1,
                    2,
                    3
                ]
            )
        )

        self.assertEqual(
            table[1].hop_count,
            2
        )

        self.assertEqual(
            table[2].hop_count,
            1
        )

        self.assertEqual(
            table[3].hop_count,
            2
        )

    def test_same_hop_as_individual_bfs(
        self
    ):

        table = (
            build_minimum_hop_route_table(
                graph=self.graph,

                sensor_ids=[
                    1,
                    2,
                    3
                ]
            )
        )

        for sensor_id in [
            1,
            2,
            3
        ]:

            direct = (
                find_minimum_hop_route(
                    self.graph,
                    sensor_id
                )
            )

            self.assertEqual(
                table[
                    sensor_id
                ].hop_count,

                direct.hop_count
            )


if __name__ == "__main__":
    unittest.main()