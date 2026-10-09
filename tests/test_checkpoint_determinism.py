from copy import deepcopy
import shutil
import tempfile
import unittest
from pathlib import Path
import yaml

from core.network import WirelessSensorNetwork
from simulation.checkpoint import (
    CHECKPOINT_MAGIC,
    CHECKPOINT_SCHEMA_VERSION,
    CheckpointError,
    auto_checkpoint,
    create_checkpoint_bytes,
    restore_checkpoint_bytes,
    save_checkpoint_file,
)
from simulation.simulator import WSNSimulator
from topology.deployment import create_sink, deploy_sensors


class CheckpointDeterminismTest(unittest.TestCase):

    def setUp(self):
        with open("config.yaml", "r", encoding="utf-8") as f:
            self.base_config = yaml.safe_load(f)

        # Use 100 sensors for fast and thorough testing
        self.config_a = deepcopy(self.base_config)
        self.config_a["network"]["num_sensors"] = 100
        self.config_a["sensor_types"] = {
            "temperature": 20,
            "humidity": 20,
            "pm25": 20,
            "wind": 20,
            "water_quality": 20,
        }
        self.config_b = deepcopy(self.config_a)

    def _build_sim(self, config):
        sensors = deploy_sensors(config)
        sink = create_sink(config)
        net = WirelessSensorNetwork(sensors=sensors, sink=sink)
        net.build_topology()
        return WSNSimulator(network=net, config=config)

    def test_continuous_equals_restored(self):
        """
        Critical requirement:
        Run 60 rounds continuously == Run 30 -> Save -> Restore -> Run 30.
        """
        sim_a = self._build_sim(self.config_a)
        sim_b = self._build_sim(self.config_b)

        # Run A: 60 rounds continuously
        for _ in range(60):
            sim_a.run_round()

        # Run B: 30 rounds -> save -> restore -> 30 rounds
        for _ in range(30):
            sim_b.run_round()

        chk_bytes = create_checkpoint_bytes(sim_b, self.config_b)
        checkpoint = restore_checkpoint_bytes(chk_bytes)
        restored = checkpoint["simulator"]

        for _ in range(30):
            restored.run_round()

        # 1. Round & Packet metrics comparison
        self.assertEqual(sim_a.current_round, restored.current_round)
        self.assertEqual(sim_a.generated_packets, restored.generated_packets)
        self.assertEqual(sim_a.delivered_packets, restored.delivered_packets)
        self.assertEqual(sim_a.dropped_packets, restored.dropped_packets)
        self.assertEqual(sim_a.total_energy_consumed_j, restored.total_energy_consumed_j)

        # 2. Sensor state comparison
        for sa, sb in zip(sim_a.network.sensors, restored.network.sensors):
            self.assertEqual(sa.node_id, sb.node_id)
            self.assertAlmostEqual(sa.remaining_energy, sb.remaining_energy, places=9)
            self.assertEqual(sa.forwarded_packets, sb.forwarded_packets)
            self.assertEqual(sa.death_round, sb.death_round)

        # 3. LB-ECMHR load tracker comparison
        tracker_a = sim_a.route_manager.load_tracker
        tracker_b = restored.route_manager.load_tracker
        self.assertEqual(tracker_a.overloaded_nodes, tracker_b.overloaded_nodes)
        self.assertEqual(tracker_a.recent_forwarded, tracker_b.recent_forwarded)
        self.assertEqual(tracker_a.load_factors, tracker_b.load_factors)

        # 4. Environment generator & RNG comparison
        rng_state_a = sim_a.environment_generator.rng.bit_generator.state
        rng_state_b = restored.environment_generator.rng.bit_generator.state
        self.assertEqual(rng_state_a, rng_state_b)
        self.assertEqual(
            sim_a.environment_generator.node_state,
            restored.environment_generator.node_state
        )

        # 5. Check next round measurement identity
        s0_a = sim_a.network.sensors[0]
        s0_b = restored.network.sensors[0]
        m_a = sim_a.environment_generator.generate(s0_a, 61, 61 * 3600)
        m_b = restored.environment_generator.generate(s0_b, 61, 61 * 3600)
        self.assertEqual(m_a.value, m_b.value)

        # 6. Collector comparison
        self.assertEqual(
            len(sim_a.environment_collector.generated_records),
            len(restored.environment_collector.generated_records)
        )
        self.assertEqual(
            len(sim_a.environment_collector.received_records),
            len(restored.environment_collector.received_records)
        )

        # 7. Simulation history comparison
        self.assertEqual(len(sim_a.history), len(restored.history))
        self.assertEqual(sim_a.history, restored.history)

    def test_validate_boundary_prevents_mid_round_save(self):
        sim = self._build_sim(self.config_a)
        sim.round_in_progress = True
        with self.assertRaises(CheckpointError):
            create_checkpoint_bytes(sim, self.config_a)

    def test_tampered_checkpoint_rejected(self):
        sim = self._build_sim(self.config_a)
        sim.run_round()
        chk_bytes = create_checkpoint_bytes(sim, self.config_a)

        # 1. Corrupt byte in the middle of compressed stream
        corrupted = bytearray(chk_bytes)
        corrupted[len(corrupted) // 2] ^= 0xFF
        with self.assertRaises(CheckpointError):
            restore_checkpoint_bytes(bytes(corrupted))

        # 2. Tampered SHA256 payload mismatch
        import io, gzip, pickle
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="wb") as gz:
            pickle.dump({"sha256": "0" * 64, "payload": b"tampered_payload"}, gz)
        with self.assertRaises(CheckpointError):
            restore_checkpoint_bytes(buffer.getvalue())

    def test_auto_checkpoint_rotation(self):
        temp_dir = Path(tempfile.mkdtemp())
        try:
            sim = self._build_sim(self.config_a)
            chk_config = {
                "auto_save": True,
                "interval_rounds": 5,
                "directory": str(temp_dir),
                "keep_last": 2,
            }

            for _ in range(15):
                sim.run_round()
                auto_checkpoint(sim, self.config_a, chk_config)

            # Rounds 5, 10, 15 were saved. With keep_last=2, only 10 and 15 should remain.
            saved_files = sorted(temp_dir.glob("checkpoint_*.wsnchk.gz"))
            self.assertEqual(len(saved_files), 2)
            self.assertTrue(saved_files[0].name.endswith("00000010.wsnchk.gz"))
            self.assertTrue(saved_files[1].name.endswith("00000015.wsnchk.gz"))

            # Restoring one of the autosaved files works
            data = saved_files[1].read_bytes()
            checkpoint = restore_checkpoint_bytes(data)
            self.assertEqual(checkpoint["round"], 15)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
