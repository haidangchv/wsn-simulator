import unittest

from core.network import (
    WirelessSensorNetwork
)
from core.sensor import SensorNode
from core.sink import SinkNode
from routing.route_manager import (
    RouteManager
)


def create_sensor(
    node_id: int,
    energy: float = 2.0
) -> SensorNode:

    return SensorNode(
        node_id=node_id,
        x=0.0,
        y=0.0,
        sensor_type="temperature",
        initial_energy=2.0,
        remaining_energy=energy,
        transmission_range=200.0
    )


class RouteManagerMidRoundRerouteTest(
    unittest.TestCase
):

    def setUp(self):

        self.config = {
            "sensor": {
                "energy_threshold_ratio": 0.20
            },
            "routing": {
                "algorithm": "ecmhr",
                "allow_emergency_mode": False,
                "emergency_threshold_ratio": 0.10
            }
        }

        self.s1 = create_sensor(1, 2.0)
        self.s2 = create_sensor(2, 2.0)
        self.s3 = create_sensor(3, 2.0)
        self.sink = SinkNode(x=100.0, y=100.0)

        self.network = WirelessSensorNetwork(
            sensors=[
                self.s1,
                self.s2,
                self.s3
            ],
            sink=self.sink
        )

        # Path 1: 1 -> 2 -> SINK (distance: 50 + 50 = 100m, preferred)
        self.network.graph.add_edge(
            1,
            2,
            distance=50.0
        )
        self.network.graph.add_edge(
            2,
            "SINK",
            distance=50.0
        )

        # Path 2 (Alternative): 1 -> 3 -> SINK (distance: 60 + 60 = 120m)
        self.network.graph.add_edge(
            1,
            3,
            distance=60.0
        )
        self.network.graph.add_edge(
            3,
            "SINK",
            distance=60.0
        )

        self.route_manager = RouteManager(
            network=self.network,
            config=self.config,
            algorithm="ecmhr"
        )

    def test_mid_round_reroute_when_relay_energy_drops(
        self
    ):
        """
        Step 5.5.13: Test reroute mid-round.

        When a relay node drops below the 20% energy threshold
        (0.40 J for 2.0 J initial battery) after transmitting a packet,
        the next packet request must detect the invalid route via
        _route_is_valid(), trigger on-demand reroute, and update
        the route table to an alternative path.
        """

        # Round starts: RouteManager builds routing table
        self.route_manager.prepare_round()

        self.assertEqual(
            self.route_manager.route_table_builds,
            1
        )

        # First request: Route is cached via relay 2
        route_1 = (
            self.route_manager.get_route(1)
        )

        self.assertIsNotNone(
            route_1
        )

        self.assertEqual(
            route_1.path,
            [1, 2, "SINK"]
        )

        self.assertEqual(
            self.route_manager.route_table_hits,
            1
        )

        self.assertEqual(
            self.route_manager.on_demand_reroutes,
            0
        )

        # Mid-round energy drop:
        # Relay 2 consumes energy down to 0.39 J (<= 20% threshold of 0.40 J)
        self.s2.remaining_energy = 0.39

        self.s2.update_state(
            energy_threshold_ratio=0.20
        )

        self.assertEqual(
            self.s2.state,
            "LOW_ENERGY"
        )

        # Next packet request for sensor 1:
        # Cached route [1, 2, SINK] is now INVALID because relay 2 is LOW_ENERGY.
        # RouteManager must detect this, trigger _reroute, and return path via relay 3.
        route_2 = (
            self.route_manager.get_route(1)
        )

        self.assertIsNotNone(
            route_2
        )

        # Verify it successfully rerouted through sensor 3
        self.assertEqual(
            route_2.path,
            [1, 3, "SINK"]
        )

        # Verify on-demand reroute counter increased
        self.assertEqual(
            self.route_manager.on_demand_reroutes,
            1
        )

        # Verify the route table is updated with the new valid route
        self.assertEqual(
            self.route_manager.route_table[1].path,
            [1, 3, "SINK"]
        )

        # Next request for sensor 1 should now HIT the updated cache
        route_3 = (
            self.route_manager.get_route(1)
        )

        self.assertEqual(
            route_3.path,
            [1, 3, "SINK"]
        )

        self.assertEqual(
            self.route_manager.route_table_hits,
            2
        )

        self.assertEqual(
            self.route_manager.on_demand_reroutes,
            1
        )

    def test_mid_round_reroute_when_relay_dies(
        self
    ):
        """
        Verify on-demand rerouting when an intermediate relay dies
        completely (remaining_energy = 0.0).
        """

        self.route_manager.prepare_round()

        # Initial route uses relay 2
        route = (
            self.route_manager.get_route(1)
        )

        self.assertEqual(
            route.path,
            [1, 2, "SINK"]
        )

        # Relay 2 completely exhausts battery mid-round
        self.s2.remaining_energy = 0.0

        self.s2.update_state(
            energy_threshold_ratio=0.20
        )

        self.assertEqual(
            self.s2.state,
            "DEAD"
        )

        # RouteManager must invalidate cached route and reroute via 3
        rerouted = (
            self.route_manager.get_route(1)
        )

        self.assertEqual(
            rerouted.path,
            [1, 3, "SINK"]
        )

        self.assertEqual(
            self.route_manager.on_demand_reroutes,
            1
        )


if __name__ == "__main__":
    unittest.main()
