import math

import numpy as np

from data.models import SensorMeasurement


class EnvironmentalDataGenerator:
    """
    Generate spatially and temporally correlated
    environmental sensor measurements.
    """

    UNIT_MAP = {
        "temperature": "°C",
        "humidity": "%",
        "pm25": "µg/m³",
        "wind": "m/s",
        "water_quality": "score"
    }

    def __init__(
        self,
        config: dict
    ):

        self.config = config

        self.environment_config = (
            config["environment"]
        )

        self.width = float(
            config["network"]["width_m"]
        )

        self.height = float(
            config["network"]["height_m"]
        )

        self.period = int(
            self.environment_config[
                "temporal_period_rounds"
            ]
        )

        self.smoothing = float(
            self.environment_config[
                "temporal_smoothing"
            ]
        )

        seed = int(
            config["network"]["random_seed"]
        )

        # Separate random stream from topology
        # generation.
        self.rng = np.random.default_rng(
            seed + 10000
        )

        self.previous_values = {}

    @staticmethod
    def _gaussian_hotspot(
        x: float,
        y: float,
        center_x: float,
        center_y: float,
        sigma: float
    ) -> float:

        distance_squared = (
            (x - center_x) ** 2
            +
            (y - center_y) ** 2
        )

        return math.exp(
            -distance_squared
            /
            (2 * sigma ** 2)
        )

    def _normalized_position(
        self,
        sensor
    ) -> tuple[float, float]:

        return (
            sensor.x / self.width,
            sensor.y / self.height
        )

    def _temporal_phase(
        self,
        round_number: int
    ) -> float:

        return (
            2
            * math.pi
            * round_number
            / self.period
        )

    def _temperature_target(
        self,
        sensor,
        round_number
    ) -> float:

        x, y = (
            self._normalized_position(
                sensor
            )
        )

        phase = self._temporal_phase(
            round_number
        )

        # General spatial gradient
        spatial_gradient = (
            2.5 * (x - 0.5)
            +
            1.2
            * math.sin(
                2 * math.pi * y
            )
        )

        # Synthetic urban heat island.
        heat_hotspot = (
            4.0
            * self._gaussian_hotspot(
                x,
                y,
                0.72,
                0.35,
                0.16
            )
        )

        temporal = (
            2.5
            * math.sin(
                phase - math.pi / 2
            )
        )

        return (
            30.0
            +
            spatial_gradient
            +
            heat_hotspot
            +
            temporal
        )

    def _humidity_target(
        self,
        sensor,
        round_number
    ) -> float:

        x, y = (
            self._normalized_position(
                sensor
            )
        )

        phase = self._temporal_phase(
            round_number
        )

        spatial = (
            6.0 * (0.5 - x)
            +
            4.0
            * math.sin(
                math.pi * y
            )
        )

        temporal = (
            7.0
            * math.sin(
                phase + math.pi / 2
            )
        )

        dry_hotspot = (
            -12.0
            * self._gaussian_hotspot(
                x,
                y,
                0.72,
                0.35,
                0.18
            )
        )

        return (
            68.0
            +
            spatial
            +
            temporal
            +
            dry_hotspot
        )

    def _pm25_target(
        self,
        sensor,
        round_number
    ) -> float:

        x, y = (
            self._normalized_position(
                sensor
            )
        )

        phase = self._temporal_phase(
            round_number
        )

        pollution_hotspot_1 = (
            55.0
            * self._gaussian_hotspot(
                x,
                y,
                0.78,
                0.68,
                0.14
            )
        )

        pollution_hotspot_2 = (
            28.0
            * self._gaussian_hotspot(
                x,
                y,
                0.30,
                0.42,
                0.18
            )
        )

        temporal = (
            10.0
            *
            (
                1
                +
                math.sin(
                    phase
                )
            )
            / 2
        )

        return (
            18.0
            +
            pollution_hotspot_1
            +
            pollution_hotspot_2
            +
            temporal
        )

    def _wind_target(
        self,
        sensor,
        round_number
    ) -> float:

        x, y = (
            self._normalized_position(
                sensor
            )
        )

        phase = self._temporal_phase(
            round_number
        )

        spatial = (
            1.0
            +
            1.8 * y
            -
            0.8 * x
        )

        temporal = (
            0.8
            * math.sin(
                phase + 0.7
            )
        )

        sheltered_zone = (
            -1.2
            * self._gaussian_hotspot(
                x,
                y,
                0.60,
                0.50,
                0.17
            )
        )

        return (
            2.0
            +
            spatial
            +
            temporal
            +
            sheltered_zone
        )

    def _water_quality_target(
        self,
        sensor,
        round_number
    ) -> float:

        x, y = (
            self._normalized_position(
                sensor
            )
        )

        phase = self._temporal_phase(
            round_number
        )

        pollution_area = (
            -40.0
            * self._gaussian_hotspot(
                x,
                y,
                0.25,
                0.78,
                0.16
            )
        )

        secondary_area = (
            -18.0
            * self._gaussian_hotspot(
                x,
                y,
                0.70,
                0.65,
                0.20
            )
        )

        temporal = (
            3.0
            * math.sin(
                phase / 2
            )
        )

        return (
            86.0
            +
            pollution_area
            +
            secondary_area
            +
            temporal
        )

    def _target_value(
        self,
        sensor,
        round_number
    ) -> float:

        sensor_type = (
            sensor.sensor_type
        )

        if sensor_type == "temperature":

            return (
                self._temperature_target(
                    sensor,
                    round_number
                )
            )

        if sensor_type == "humidity":

            return (
                self._humidity_target(
                    sensor,
                    round_number
                )
            )

        if sensor_type == "pm25":

            return (
                self._pm25_target(
                    sensor,
                    round_number
                )
            )

        if sensor_type == "wind":

            return (
                self._wind_target(
                    sensor,
                    round_number
                )
            )

        if (
            sensor_type
            == "water_quality"
        ):

            return (
                self._water_quality_target(
                    sensor,
                    round_number
                )
            )

        raise ValueError(
            f"Unsupported sensor type: "
            f"{sensor_type}"
        )

    def _noise(
        self,
        sensor_type: str
    ) -> float:

        std = float(
            self.environment_config[
                "noise"
            ][
                sensor_type
            ]
        )

        return float(
            self.rng.normal(
                0.0,
                std
            )
        )

    def _clamp(
        self,
        sensor_type: str,
        value: float
    ) -> float:

        bounds = (
            self.environment_config[
                "bounds"
            ][
                sensor_type
            ]
        )

        minimum = float(
            bounds["min"]
        )

        maximum = float(
            bounds["max"]
        )

        return max(
            minimum,
            min(
                maximum,
                value
            )
        )

    def generate(
        self,
        sensor,
        round_number: int,
        simulation_time_seconds: float
    ) -> SensorMeasurement:

        target = self._target_value(
            sensor,
            round_number
        )

        previous = (
            self.previous_values.get(
                sensor.node_id
            )
        )

        if previous is None:

            value = (
                target
                +
                self._noise(
                    sensor.sensor_type
                )
            )

        else:

            value = (
                self.smoothing
                * previous
                +
                (
                    1.0
                    -
                    self.smoothing
                )
                * target
                +
                self._noise(
                    sensor.sensor_type
                )
            )

        value = self._clamp(
            sensor.sensor_type,
            value
        )

        self.previous_values[
            sensor.node_id
        ] = value

        return SensorMeasurement(
            source_id=(
                sensor.node_id
            ),

            sensor_type=(
                sensor.sensor_type
            ),

            round_number=(
                round_number
            ),

            simulation_time_seconds=(
                simulation_time_seconds
            ),

            value=round(
                value,
                3
            ),

            unit=(
                self.UNIT_MAP[
                    sensor.sensor_type
                ]
            )
        )