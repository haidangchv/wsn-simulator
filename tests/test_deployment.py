import unittest
from collections import Counter
from pathlib import Path

import yaml

from topology.deployment import deploy_sensors


def load_config():

    config_path = (
        Path(__file__).parent.parent
        / "config.yaml"
    )

    with open(
        config_path,
        "r",
        encoding="utf-8"
    ) as file:
        return yaml.safe_load(file)


class DeploymentTest(unittest.TestCase):

    def setUp(self):

        self.config = load_config()

        self.sensors = deploy_sensors(
            self.config
        )

    def test_sensor_count(self):

        self.assertEqual(
            len(self.sensors),
            500
        )

    def test_unique_ids(self):

        ids = [
            sensor.node_id
            for sensor in self.sensors
        ]

        self.assertEqual(
            len(ids),
            len(set(ids))
        )

    def test_sensor_positions(self):

        width = (
            self.config["network"]["width_m"]
        )

        height = (
            self.config["network"]["height_m"]
        )

        for sensor in self.sensors:

            self.assertGreaterEqual(
                sensor.x,
                0
            )

            self.assertLessEqual(
                sensor.x,
                width
            )

            self.assertGreaterEqual(
                sensor.y,
                0
            )

            self.assertLessEqual(
                sensor.y,
                height
            )

    def test_initial_energy(self):

        expected_energy = (
            self.config
            ["sensor"]
            ["initial_energy_j"]
        )

        for sensor in self.sensors:

            self.assertEqual(
                sensor.remaining_energy,
                expected_energy
            )

    def test_sensor_type_count(self):

        counter = Counter(
            sensor.sensor_type
            for sensor in self.sensors
        )

        self.assertEqual(
            counter["temperature"],
            100
        )

        self.assertEqual(
            counter["humidity"],
            100
        )

        self.assertEqual(
            counter["pm25"],
            100
        )

        self.assertEqual(
            counter["wind"],
            100
        )

        self.assertEqual(
            counter["water_quality"],
            100
        )

    def test_reproducible_deployment(self):

        sensors_1 = deploy_sensors(
            self.config
        )

        sensors_2 = deploy_sensors(
            self.config
        )

        for s1, s2 in zip(
            sensors_1,
            sensors_2
        ):

            self.assertEqual(
                s1.x,
                s2.x
            )

            self.assertEqual(
                s1.y,
                s2.y
            )

            self.assertEqual(
                s1.sensor_type,
                s2.sensor_type
            )

if __name__ == "__main__":
    unittest.main()