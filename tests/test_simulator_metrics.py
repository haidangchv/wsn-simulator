import unittest

from core.network import (
    WirelessSensorNetwork
)
from core.sensor import SensorNode
from core.sink import SinkNode
from simulation.simulator import (
    WSNSimulator
)


class SimulatorMetricsTest(
    unittest.TestCase
):

    def setUp(self):

        self.config = {
            "sensor": {
                "energy_threshold_ratio": 0.20
            },

            "packet": {
                "payload_size_bytes": 128,
                "sampling_interval_seconds": 10
            },

            "energy": {
                "e_elec_nj_per_bit": 50,
                "eps_fs_pj_per_bit_m2": 10,
                "eps_mp_pj_per_bit_m4": 0.0013,
                "per_hop_delay_ms": 10
            }
        }

        sensor = SensorNode(
            node_id=1,
            x=0,
            y=0,
            sensor_type="temperature",
            initial_energy=2.0,
            remaining_energy=2.0,
            transmission_range=200
        )

        sink = SinkNode(
            x=50,
            y=0
        )

        self.network = WirelessSensorNetwork(
            sensors=[sensor],
            sink=sink
        )

        self.network.graph.add_node(
            1
        )

        self.network.graph.add_node(
            "SINK"
        )

        self.network.graph.add_edge(
            1,
            "SINK",
            distance=50.0
        )

        self.simulator = WSNSimulator(
            network=self.network,
            config=self.config
        )

    def test_one_round(self):

        self.simulator.run_round()

        metrics = (
            self.simulator.get_metrics()
        )

        self.assertEqual(
            metrics["round"],
            1
        )

        self.assertEqual(
            metrics["generated_packets"],
            1
        )

        self.assertEqual(
            metrics["delivered_packets"],
            1
        )

        self.assertEqual(
            metrics["dropped_packets"],
            0
        )

        self.assertEqual(
            metrics["pdr"],
            1.0
        )

    def test_throughput(self):

        self.simulator.run_round()

        metrics = (
            self.simulator.get_metrics()
        )

        expected = (
            128 * 8 / 10
        )

        self.assertAlmostEqual(
            metrics["throughput_bps"],
            expected
        )

    def test_delay(self):

        self.simulator.run_round()

        metrics = (
            self.simulator.get_metrics()
        )

        self.assertEqual(
            metrics["average_delay_ms"],
            10
        )

    def test_average_hop(self):

        self.simulator.run_round()

        metrics = (
            self.simulator.get_metrics()
        )

        self.assertEqual(
            metrics["average_hop_count"],
            1
        )

    def test_history(self):

        self.simulator.run(
            rounds=5
        )

        self.assertEqual(
            len(self.simulator.history),
            5
        )

    def test_energy_efficiency_positive(
        self
    ):

        self.simulator.run_round()

        metrics = (
            self.simulator.get_metrics()
        )

        self.assertGreater(
            metrics[
                "energy_efficiency_bits_per_j"
            ],
            0
        )


if __name__ == "__main__":
    unittest.main()