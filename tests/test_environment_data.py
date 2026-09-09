import unittest

from core.sensor import SensorNode
from data.generator import (
    EnvironmentalDataGenerator
)


class EnvironmentalDataTest(
    unittest.TestCase
):

    def setUp(self):

        self.config = {
            "network": {
                "width_m": 2000,
                "height_m": 2000,
                "random_seed": 42
            },

            "environment": {

                "temporal_period_rounds":
                    144,

                "temporal_smoothing":
                    0.85,

                "noise": {
                    "temperature": 0.15,
                    "humidity": 0.40,
                    "pm25": 1.20,
                    "wind": 0.12,
                    "water_quality": 0.40
                },

                "bounds": {

                    "temperature": {
                        "min": 18,
                        "max": 45
                    },

                    "humidity": {
                        "min": 20,
                        "max": 100
                    },

                    "pm25": {
                        "min": 0,
                        "max": 200
                    },

                    "wind": {
                        "min": 0,
                        "max": 15
                    },

                    "water_quality": {
                        "min": 0,
                        "max": 100
                    }
                }
            }
        }

    def create_sensor(
        self,
        sensor_type
    ):

        return SensorNode(
            node_id=1,
            x=1000,
            y=1000,
            sensor_type=sensor_type,
            initial_energy=2,
            remaining_energy=2,
            transmission_range=200
        )

    def test_all_sensor_types(
        self
    ):

        for sensor_type in [
            "temperature",
            "humidity",
            "pm25",
            "wind",
            "water_quality"
        ]:

            generator = (
                EnvironmentalDataGenerator(
                    self.config
                )
            )

            sensor = (
                self.create_sensor(
                    sensor_type
                )
            )

            measurement = (
                generator.generate(
                    sensor,
                    round_number=1,
                    simulation_time_seconds=10
                )
            )

            self.assertIsNotNone(
                measurement.value
            )

    def test_reproducible(
        self
    ):

        sensor = self.create_sensor(
            "temperature"
        )

        generator_1 = (
            EnvironmentalDataGenerator(
                self.config
            )
        )

        generator_2 = (
            EnvironmentalDataGenerator(
                self.config
            )
        )

        value_1 = (
            generator_1.generate(
                sensor,
                1,
                10
            ).value
        )

        value_2 = (
            generator_2.generate(
                sensor,
                1,
                10
            ).value
        )

        self.assertEqual(
            value_1,
            value_2
        )

    def test_temporal_correlation_smoothness(
        self
    ):
        generator = EnvironmentalDataGenerator(
            self.config
        )
        sensor = self.create_sensor("temperature")

        values = []
        for r in range(1, 20):
            m = generator.generate(sensor, r, r * 10)
            values.append(m.value)

        # Check that consecutive round differences are small and smooth (no erratic jumps)
        for i in range(len(values) - 1):
            diff = abs(values[i + 1] - values[i])
            self.assertLess(
                diff,
                2.0,
                f"Consecutive round jump too large: {diff} between {values[i]} and {values[i+1]}"
            )

    def test_spatial_hotspot_correlation(
        self
    ):
        generator = EnvironmentalDataGenerator(
            self.config
        )

        # PM2.5 has hotspot around (0.78 * 2000 = 1560, 0.68 * 2000 = 1360)
        pm_hotspot = SensorNode(10, 1560, 1360, "pm25", 2.0, 2.0, 200)
        pm_away = SensorNode(11, 200, 200, "pm25", 2.0, 2.0, 200)

        pm_hotspot_val = generator.generate(pm_hotspot, 1, 10).value
        pm_away_val = generator.generate(pm_away, 1, 10).value

        # Hotspot area should have significantly higher PM2.5 than away area
        self.assertGreater(pm_hotspot_val, pm_away_val + 20.0)

        # Temperature hotspot is at (0.72 * 2000 = 1440, 0.35 * 2000 = 700)
        temp_hotspot = SensorNode(12, 1440, 700, "temperature", 2.0, 2.0, 200)
        temp_away = SensorNode(13, 200, 200, "temperature", 2.0, 2.0, 200)

        temp_hotspot_val = generator.generate(temp_hotspot, 1, 10).value
        temp_away_val = generator.generate(temp_away, 1, 10).value

        # Hotspot area should be warmer than away area
        self.assertGreater(temp_hotspot_val, temp_away_val + 2.0)


if __name__ == "__main__":
    unittest.main()