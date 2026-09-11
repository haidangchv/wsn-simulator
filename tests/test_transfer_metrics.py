import unittest

import networkx as nx

from core.network import WirelessSensorNetwork
from core.sensor import SensorNode
from simulation.simulator import WSNSimulator
from topology.deployment import SinkNode


class TransferMetricTest(
    unittest.TestCase
):

    def test_128_byte_tx_time_at_250kbps(
        self
    ):

        packet_bytes = 128

        data_rate = 250000

        tx_ms = (
            packet_bytes
            *
            8
            /
            data_rate
            *
            1000
        )

        self.assertAlmostEqual(
            tx_ms,
            4.096,
            places=3
        )

    def test_ecmhr_energy_hole_connectivity(
        self
    ):
        """
        Topology:
        Sensor 1 (2.0 J) --- Sensor 2 (0.3 J) --- SINK
        Initial Energy: 2.0 J each
        Threshold ratio: 0.20 (0.4 J)

        Sensor 2 has 0.3 J <= 0.4 J (LOW_ENERGY), so it cannot relay.
        Sensor 1 has no valid relay to SINK -> disconnected in ECMHR.
        Sensor 2 can still reach SINK directly as source -> connected in ECMHR.
        """
        s1 = SensorNode(
            node_id=1,
            x=100.0,
            y=500.0,
            sensor_type="temperature",
            initial_energy=2.0,
            remaining_energy=2.0,
            transmission_range=150.0
        )

        s2 = SensorNode(
            node_id=2,
            x=200.0,
            y=500.0,
            sensor_type="humidity",
            initial_energy=2.0,
            remaining_energy=0.3,
            transmission_range=150.0
        )
        s2.update_state(0.20)

        sink = SinkNode(
            x=300.0,
            y=500.0
        )

        net = WirelessSensorNetwork(
            sensors=[s1, s2],
            sink=sink
        )
        net.build_topology()

        config = {
            "sensor": {
                "energy_threshold_ratio": 0.20,
                "initial_energy_j": 2.0,
                "transmission_range_m": 150.0
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
            },
            "radio": {
                "data_rate_bps": 250000,
                "processing_delay_ms_per_hop": 1.0,
                "propagation_speed_m_s": 300000000
            },
            "routing": {
                "algorithm": "ecmhr",
                "allow_emergency_mode": False,
                "emergency_threshold_ratio": 0.10
            },
            "environment": {
                "enabled": False
            }
        }

        sim = WSNSimulator(
            network=net,
            config=config,
            routing_algorithm="ecmhr"
        )

        connected_ids = sim.get_connected_alive_sensor_ids()

        # Sensor 2 is directly connected to Sink
        self.assertIn(2, connected_ids)

        # Sensor 1 requires Sensor 2 as relay, but Sensor 2 is low energy
        self.assertNotIn(1, connected_ids)

        metrics = sim.get_connectivity_metrics()
        self.assertEqual(metrics["connected_alive_nodes"], 1)
        self.assertEqual(metrics["disconnected_alive_nodes"], 1)
        self.assertAlmostEqual(metrics["connectivity_ratio"], 0.5)


if __name__ == "__main__":
    unittest.main()
