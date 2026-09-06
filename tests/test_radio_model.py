import unittest
from core.sensor import SensorNode
from energy.radio_model import (
    RadioEnergyModel
)


class RadioEnergyModelTest(
    unittest.TestCase
):

    def setUp(self):

        self.radio = RadioEnergyModel(
            e_elec_j_per_bit=50e-9,

            eps_fs_j_per_bit_m2=10e-12,

            eps_mp_j_per_bit_m4=(
                0.0013e-12
            )
        )

    def test_crossover_distance(self):

        self.assertAlmostEqual(
            self.radio.crossover_distance_m,
            87.7058,
            places=3
        )

    def test_receive_energy(self):

        energy = self.radio.rx_energy(
            128
        )

        self.assertAlmostEqual(
            energy,
            51.2e-6
        )

    def test_short_distance_tx(self):

        energy = self.radio.tx_energy(
            packet_size_bytes=128,
            distance_m=50
        )

        expected = 76.8e-6

        self.assertAlmostEqual(
            energy,
            expected
        )

    def test_low_energy_state(self):

        sensor = SensorNode(
            node_id=1,
            x=0,
            y=0,
            sensor_type="temperature",
            initial_energy=2.0,
            remaining_energy=2.0,
            transmission_range=200
        )

        sensor.consume_energy(
            amount_j=1.7,
            energy_threshold_ratio=0.20
        )

        self.assertEqual(
            sensor.state,
            "LOW_ENERGY"
        )

        self.assertFalse(
            sensor.relay_enabled
        )

    def test_dead_state(self):

        sensor = SensorNode(
            node_id=1,
            x=0,
            y=0,
            sensor_type="temperature",
            initial_energy=2.0,
            remaining_energy=0.1,
            transmission_range=200
        )

        sensor.consume_energy(
            amount_j=0.1,
            energy_threshold_ratio=0.20
        )

        self.assertEqual(
            sensor.state,
            "DEAD"
        )

        self.assertEqual(
            sensor.remaining_energy,
            0
        )

    def test_longer_distance_costs_more(self):

        energy_50 = (
            self.radio.tx_energy(
                128,
                50
            )
        )

        energy_150 = (
            self.radio.tx_energy(
                128,
                150
            )
        )

        self.assertGreater(
            energy_150,
            energy_50
        )


if __name__ == "__main__":
    unittest.main()