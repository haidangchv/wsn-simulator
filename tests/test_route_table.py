import unittest

import networkx as nx

from routing.minimum_hop import (
    find_minimum_hop_route
)
from routing.route_table import (
    build_minimum_hop_route_table
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