import unittest

from core.network import WirelessSensorNetwork
from core.sensor import SensorNode
from core.sink import SinkNode
from routing.ecmhr import ECMHRRouter, find_ecmhr_route


def create_sensor(node_id: int, energy: float = 2.0, x: float = 0.0, y: float = 0.0) -> SensorNode:
    return SensorNode(
        node_id=node_id,
        x=x,
        y=y,
        sensor_type="temperature",
        initial_energy=2.0,
        remaining_energy=energy,
        transmission_range=200.0
    )


class ECMHRRouterTest(unittest.TestCase):

    def setUp(self):
        self.sink = SinkNode(x=100.0, y=100.0)

    def test_direct_connection_to_sink(self):
        s1 = create_sensor(1, 2.0, 50.0, 50.0)
        net = WirelessSensorNetwork(sensors=[s1], sink=self.sink)
        net.graph.add_edge(1, "SINK", distance=50.0)

        router = ECMHRRouter(network=net, energy_threshold_ratio=0.15)
        route = router.route_source(1)

        self.assertIsNotNone(route)
        self.assertEqual(route.path, [1, "SINK"])
        self.assertEqual(route.hop_count, 1)

    def test_avoid_low_energy_relay(self):
        """
        Topology:
        Source 1 -> Relay 2 -> Sink (hop=2, distance=100m, Relay 2 has low energy 0.25J <= 0.30J threshold)
        Source 1 -> Relay 3 -> Sink (hop=2, distance=120m, Relay 3 has high energy 1.8J)
        ECMHR must bypass Relay 2 and choose Relay 3.
        """
        s1 = create_sensor(1, 2.0, 0.0, 0.0)
        s2 = create_sensor(2, 0.25, 50.0, 50.0)  # Low energy (12.5% <= 15%)
        s3 = create_sensor(3, 1.80, 60.0, 60.0)  # High energy (90%)

        s2.update_state(energy_threshold_ratio=0.15)
        self.assertEqual(s2.state, "LOW_ENERGY")

        net = WirelessSensorNetwork(sensors=[s1, s2, s3], sink=self.sink)
        net.graph.add_edge(1, 2, distance=50.0)
        net.graph.add_edge(2, "SINK", distance=50.0)

        net.graph.add_edge(1, 3, distance=60.0)
        net.graph.add_edge(3, "SINK", distance=60.0)

        router = ECMHRRouter(network=net, energy_threshold_ratio=0.15)
        route = router.route_source(1)

        self.assertIsNotNone(route)
        self.assertEqual(route.path, [1, 3, "SINK"])
        self.assertEqual(route.hop_count, 2)

    def test_low_energy_source_can_still_originate_data(self):
        """
        Source 1 is LOW_ENERGY (0.2J). It can still transmit its own data through
        a valid relay 2 (1.8J).
        """
        s1 = create_sensor(1, 0.2, 0.0, 0.0)
        s2 = create_sensor(2, 1.8, 50.0, 50.0)

        s1.update_state(energy_threshold_ratio=0.15)
        self.assertEqual(s1.state, "LOW_ENERGY")

        net = WirelessSensorNetwork(sensors=[s1, s2], sink=self.sink)
        net.graph.add_edge(1, 2, distance=50.0)
        net.graph.add_edge(2, "SINK", distance=50.0)

        router = ECMHRRouter(network=net, energy_threshold_ratio=0.15)
        route = router.route_source(1)

        self.assertIsNotNone(route)
        self.assertEqual(route.path, [1, 2, "SINK"])

    def test_tie_breaking_max_bottleneck_energy(self):
        """
        Two paths with same hop count:
        Path A: 1 -> 2 -> SINK (Relay 2 energy: 1.0J)
        Path B: 1 -> 3 -> SINK (Relay 3 energy: 1.6J)
        Both have hop=2 and distance=100m. ECMHR should choose Path B (higher bottleneck).
        """
        s1 = create_sensor(1, 2.0, 0.0, 0.0)
        s2 = create_sensor(2, 1.0, 50.0, 50.0)
        s3 = create_sensor(3, 1.6, 50.0, 50.0)

        net = WirelessSensorNetwork(sensors=[s1, s2, s3], sink=self.sink)
        net.graph.add_edge(1, 2, distance=50.0)
        net.graph.add_edge(2, "SINK", distance=50.0)
        net.graph.add_edge(1, 3, distance=50.0)
        net.graph.add_edge(3, "SINK", distance=50.0)

        router = ECMHRRouter(network=net, energy_threshold_ratio=0.15)
        route = router.route_source(1)

        self.assertIsNotNone(route)
        self.assertEqual(route.path, [1, 3, "SINK"])
        self.assertEqual(route.bottleneck_energy_j, 1.6)


if __name__ == "__main__":
    unittest.main()
