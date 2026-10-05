import unittest

from core.network import WirelessSensorNetwork
from core.sensor import SensorNode
from core.sink import SinkNode
from routing.lb_ecmhr import LBECMHRRouter, find_lb_ecmhr_route


def create_sensor(
    node_id: int,
    energy: float = 2.0,
    x: float = 0.0,
    y: float = 0.0
) -> SensorNode:

    sensor = SensorNode(
        node_id=node_id,
        x=x,
        y=y,
        sensor_type="temperature",
        initial_energy=2.0,
        remaining_energy=energy,
        transmission_range=200.0
    )
    sensor.update_state(
        energy_threshold_ratio=0.20
    )
    return sensor


class LBECMHRRouterTest(
    unittest.TestCase
):

    def test_1_same_hop_prefers_lower_load(
        self
    ):
        """
        Test 1:
               A (node 2, load=3.0)
             /   \
        Source    Sink
             \   /
               B (node 3, load=0.5)

        Both paths are 2 hops.
        Must select Source -> B -> Sink due to lower relay load.
        """
        sink = SinkNode(x=100.0, y=0.0)
        s_src = create_sensor(1, energy=2.0, x=0.0, y=0.0)
        s_a = create_sensor(2, energy=2.0, x=50.0, y=30.0)
        s_b = create_sensor(3, energy=2.0, x=50.0, y=-30.0)

        network = WirelessSensorNetwork(
            sensors=[s_src, s_a, s_b],
            sink=sink
        )

        network.graph.add_edge(1, 2, distance=50.0)
        network.graph.add_edge(2, "SINK", distance=50.0)
        network.graph.add_edge(1, 3, distance=50.0)
        network.graph.add_edge(3, "SINK", distance=50.0)

        router = LBECMHRRouter(
            network=network,
            energy_threshold_ratio=0.20,
            max_extra_hops=1,
            allow_overload_fallback=True
        )

        load_factors = {
            2: 3.0,
            3: 0.5
        }
        overloaded_nodes = set()

        table = router.build_route_table(
            load_factors=load_factors,
            overloaded_nodes=overloaded_nodes
        )

        route = table[1]
        self.assertIsNotNone(route)
        self.assertEqual(
            route.path,
            [1, 3, "SINK"]
        )
        self.assertEqual(
            route.hop_count,
            2
        )
        self.assertEqual(
            route.detour_hops,
            0
        )
        self.assertAlmostEqual(
            route.max_relay_load,
            0.5
        )

    def test_2_overloaded_relay_accepts_bounded_detour(
        self
    ):
        """
        Test 2:
        Source -> A -> Sink: 2 hops, but A is OVERLOADED.
        Source -> B -> C -> Sink: 3 hops (detour +1 hop).
        With max_extra_hops = 1, must select Source -> B -> C -> Sink.
        """
        sink = SinkNode(x=100.0, y=0.0)
        s_src = create_sensor(1, energy=2.0, x=0.0, y=0.0)
        s_a = create_sensor(2, energy=2.0, x=50.0, y=30.0)
        s_b = create_sensor(3, energy=2.0, x=30.0, y=-30.0)
        s_c = create_sensor(4, energy=2.0, x=70.0, y=-30.0)

        network = WirelessSensorNetwork(
            sensors=[s_src, s_a, s_b, s_c],
            sink=sink
        )

        # Path via A (2 hops)
        network.graph.add_edge(1, 2, distance=50.0)
        network.graph.add_edge(2, "SINK", distance=50.0)

        # Path via B -> C (3 hops)
        network.graph.add_edge(1, 3, distance=40.0)
        network.graph.add_edge(3, 4, distance=40.0)
        network.graph.add_edge(4, "SINK", distance=40.0)

        router = LBECMHRRouter(
            network=network,
            energy_threshold_ratio=0.20,
            max_extra_hops=1,
            allow_overload_fallback=True
        )

        load_factors = {
            2: 2.5,
            3: 0.6,
            4: 0.7
        }
        overloaded_nodes = {2}

        table = router.build_route_table(
            load_factors=load_factors,
            overloaded_nodes=overloaded_nodes
        )

        route = table[1]
        self.assertIsNotNone(route)
        self.assertEqual(
            route.path,
            [1, 3, 4, "SINK"]
        )
        self.assertEqual(
            route.hop_count,
            3
        )
        self.assertEqual(
            route.baseline_hop_count,
            2
        )
        self.assertEqual(
            route.detour_hops,
            1
        )
        self.assertFalse(
            route.used_overload_fallback
        )

    def test_3_bounded_detour_limit_and_fallback(
        self
    ):
        """
        Test 3:
        Baseline: Source -> A -> Sink: 2 hops, but A is OVERLOADED.
        Alternative: Source -> B -> C -> D -> Sink: 4 hops (+2 hops).
        With max_extra_hops = 1, the 4-hop path exceeds detour bound.
        Must fallback to the 2-hop baseline path with used_overload_fallback = True.
        """
        sink = SinkNode(x=100.0, y=0.0)
        s_src = create_sensor(1, energy=2.0)
        s_a = create_sensor(2, energy=2.0)
        s_b = create_sensor(3, energy=2.0)
        s_c = create_sensor(4, energy=2.0)
        s_d = create_sensor(5, energy=2.0)

        network = WirelessSensorNetwork(
            sensors=[s_src, s_a, s_b, s_c, s_d],
            sink=sink
        )

        # Baseline: 1 -> 2 -> SINK (2 hops)
        network.graph.add_edge(1, 2, distance=50.0)
        network.graph.add_edge(2, "SINK", distance=50.0)

        # Long detour: 1 -> 3 -> 4 -> 5 -> SINK (4 hops)
        network.graph.add_edge(1, 3, distance=25.0)
        network.graph.add_edge(3, 4, distance=25.0)
        network.graph.add_edge(4, 5, distance=25.0)
        network.graph.add_edge(5, "SINK", distance=25.0)

        router = LBECMHRRouter(
            network=network,
            energy_threshold_ratio=0.20,
            max_extra_hops=1,
            allow_overload_fallback=True
        )

        load_factors = {
            2: 2.8,
            3: 0.5,
            4: 0.5,
            5: 0.5
        }
        overloaded_nodes = {2}

        table = router.build_route_table(
            load_factors=load_factors,
            overloaded_nodes=overloaded_nodes
        )

        route = table[1]
        self.assertIsNotNone(route)
        # Cannot take 4-hop detour; falls back to 2 hops via A
        self.assertEqual(
            route.path,
            [1, 2, "SINK"]
        )
        self.assertEqual(
            route.hop_count,
            2
        )
        self.assertTrue(
            route.used_overload_fallback
        )

        # When allow_overload_fallback is False, no route should be returned
        router_no_fallback = LBECMHRRouter(
            network=network,
            energy_threshold_ratio=0.20,
            max_extra_hops=1,
            allow_overload_fallback=False
        )
        table_no_fallback = router_no_fallback.build_route_table(
            load_factors=load_factors,
            overloaded_nodes=overloaded_nodes
        )
        self.assertIsNone(
            table_no_fallback[1]
        )

    def test_4_low_energy_cannot_relay_but_can_originate(
        self
    ):
        """
        Test 4:
        Source 1 -> Relay A (2) -> Sink
        Relay A has energy = 0.3 J (15% <= 20% threshold).
        Source 1 cannot use A as relay.
        Source A itself CAN originate its own packet directly to Sink.
        """
        sink = SinkNode(x=100.0, y=0.0)
        s_src = create_sensor(1, energy=2.0)
        s_a = create_sensor(2, energy=0.30)  # Low energy (0.30/2.0 = 15%)

        self.assertEqual(
            s_a.state,
            "LOW_ENERGY"
        )
        self.assertFalse(
            s_a.relay_enabled
        )

        network = WirelessSensorNetwork(
            sensors=[s_src, s_a],
            sink=sink
        )

        network.graph.add_edge(1, 2, distance=50.0)
        network.graph.add_edge(2, "SINK", distance=50.0)

        router = LBECMHRRouter(
            network=network,
            energy_threshold_ratio=0.20,
            max_extra_hops=1,
            allow_overload_fallback=True
        )

        table = router.build_route_table(
            load_factors={},
            overloaded_nodes=set()
        )

        # Sensor 1 has NO valid route because Relay A is below energy threshold
        self.assertIsNone(
            table[1]
        )

        # Sensor 2 (LOW_ENERGY) CAN route its own packet to SINK directly
        self.assertIsNotNone(
            table[2]
        )
        self.assertEqual(
            table[2].path,
            [2, "SINK"]
        )


if __name__ == "__main__":
    unittest.main()
