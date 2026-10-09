from datetime import datetime
import math
import numpy as np

from data.models import SensorMeasurement


class EnvironmentalDataGenerator:
    """
    Sinh dữ liệu môi trường có:

    - spatial heterogeneity (Gaussian latent fields)
    - polluted / degraded regions
    - day-night cycle (24h)
    - slow temporal variation (weekly & pollution episodes)
    - temporal autocorrelation (AR(1) process)
    - measurement noise

    Quan trọng:
    Generator KHÔNG thay đổi tọa độ sensor.
    Nó chỉ sử dụng sensor.x và sensor.y để xác định trường không gian.
    """

    UNITS = {
        "temperature": "°C",
        "humidity": "%",
        "pm25": "µg/m³",
        "wind": "m/s",
        "water_quality": "score",
    }

    # Backward compatibility alias
    UNIT_MAP = UNITS

    def __init__(
        self,
        config: dict,
        seed: int | None = None
    ):

        self.config = config

        env = config.get(
            "environment",
            {}
        )

        network = config.get(
            "network",
            {}
        )

        self.width_m = float(
            network.get(
                "width_m",
                network.get(
                    "area_width_m",
                    2000
                )
            )
        )

        self.height_m = float(
            network.get(
                "height_m",
                network.get(
                    "area_height_m",
                    2000
                )
            )
        )

        # Backward compatibility aliases
        self.width = self.width_m
        self.height = self.height_m

        seed_offset = int(
            env.get(
                "seed_offset",
                10000
            )
        )

        if seed is None:
            seed = int(
                network.get(
                    "random_seed",
                    42
                )
            )

        # RNG môi trường độc lập với RNG deployment.
        self.rng = np.random.default_rng(
            seed + seed_offset
        )

        self.temporal_period = int(
            env.get(
                "temporal_period_rounds",
                24
            )
        )

        self.rho = float(
            env.get(
                "temporal_correlation",
                env.get(
                    "temporal_smoothing",
                    0.72
                )
            )
        )

        self.spatial_strength = float(
            env.get(
                "spatial_strength",
                1.0
            )
        )

        self.pollution_strength = float(
            env.get(
                "pollution_strength",
                1.0
            )
        )

        self.noise = env.get(
            "noise",
            {}
        )

        self.bounds = env.get(
            "bounds",
            {}
        )

        # Trạng thái môi trường thực bên dưới
        # trước khi cộng nhiễu cảm biến.
        self.node_state = {}

    # =====================================================
    # Utilities
    # =====================================================

    @staticmethod
    def _gaussian(
        x,
        y,
        cx,
        cy,
        sx,
        sy
    ):

        dx = (
            (x - cx)
            /
            max(sx, 1e-9)
        )

        dy = (
            (y - cy)
            /
            max(sy, 1e-9)
        )

        return math.exp(
            -0.5
            *
            (
                dx * dx
                +
                dy * dy
            )
        )

    @staticmethod
    def _cyclic_hour_distance(
        hour,
        center
    ):

        difference = abs(
            hour - center
        )

        return min(
            difference,
            24.0 - difference
        )

    @classmethod
    def _hour_peak(
        cls,
        hour,
        center,
        width
    ):

        distance = (
            cls._cyclic_hour_distance(
                hour,
                center
            )
        )

        return math.exp(
            -0.5
            *
            (
                distance
                /
                width
            ) ** 2
        )

    def _clamp(
        self,
        sensor_type,
        value
    ):

        bounds = (
            self.bounds.get(
                sensor_type
            )
        )

        if bounds is None:
            return float(value)

        if isinstance(bounds, (list, tuple)):
            low, high = bounds[0], bounds[1]
        elif isinstance(bounds, dict):
            low = bounds.get("min", float("-inf"))
            high = bounds.get("max", float("inf"))
        else:
            return float(value)

        return float(
            np.clip(
                value,
                low,
                high
            )
        )

    # =====================================================
    # Spatial latent fields
    # =====================================================

    def _spatial_fields(
        self,
        sensor
    ):

        # Chuẩn hóa tọa độ về [0, 1].
        x = (
            sensor.x
            /
            self.width_m
        )

        y = (
            sensor.y
            /
            self.height_m
        )

        # ---------------------------------------------
        # Khu công nghiệp / nguồn phát thải chính
        # ---------------------------------------------

        industrial = (
            self._gaussian(
                x,
                y,
                0.78,
                0.68,
                0.15,
                0.16
            )
        )

        # ---------------------------------------------
        # Khu giao thông đông
        # ---------------------------------------------

        traffic = (
            self._gaussian(
                x,
                y,
                0.30,
                0.42,
                0.13,
                0.17
            )
        )

        # ---------------------------------------------
        # Hiệu ứng đảo nhiệt đô thị
        # ---------------------------------------------

        urban = (
            self._gaussian(
                x,
                y,
                0.70,
                0.33,
                0.20,
                0.17
            )
        )

        # ---------------------------------------------
        # Vùng cây xanh / ẩm
        # ---------------------------------------------

        green = (
            self._gaussian(
                x,
                y,
                0.40,
                0.75,
                0.22,
                0.18
            )
        )

        # ---------------------------------------------
        # Ô nhiễm chất lượng nước
        # ---------------------------------------------

        water_pollution_1 = (
            self._gaussian(
                x,
                y,
                0.80,
                0.72,
                0.18,
                0.14
            )
        )

        water_pollution_2 = (
            self._gaussian(
                x,
                y,
                0.20,
                0.80,
                0.15,
                0.17
            )
        )

        water_pollution = max(
            water_pollution_1,
            water_pollution_2
        )

        # ---------------------------------------------
        # Vùng khuất gió
        # ---------------------------------------------

        sheltered = (
            self._gaussian(
                x,
                y,
                0.58,
                0.48,
                0.22,
                0.20
            )
        )

        return {
            "industrial":
                industrial,

            "traffic":
                traffic,

            "urban":
                urban,

            "green":
                green,

            "water_pollution":
                water_pollution,

            "sheltered":
                sheltered,
        }

    # =====================================================
    # Temporal latent fields
    # =====================================================

    def _temporal_fields(
        self,
        round_number
    ):

        # 1 round = 1 giờ.
        hour = (
            (round_number - 1)
            % 24
        )

        elapsed_days = (
            (round_number - 1)
            /
            24.0
        )

        # ---------------------------------------------
        # Chu kỳ nhiệt độ:
        # thấp ban đêm, cao khoảng 14h.
        # ---------------------------------------------

        temperature_cycle = math.sin(
            2.0
            *
            math.pi
            *
            (
                hour - 8.0
            )
            /
            24.0
        )

        # ---------------------------------------------
        # PM2.5 cao hơn vào giờ giao thông
        # sáng / chiều.
        # ---------------------------------------------

        morning_rush = (
            self._hour_peak(
                hour,
                center=8.0,
                width=2.0
            )
        )

        evening_rush = (
            self._hour_peak(
                hour,
                center=18.0,
                width=2.5
            )
        )

        traffic_cycle = max(
            morning_rush,
            evening_rush
        )

        # ---------------------------------------------
        # Gió thường mạnh hơn buổi trưa / chiều.
        # ---------------------------------------------

        wind_afternoon = (
            self._hour_peak(
                hour,
                center=14.0,
                width=4.0
            )
        )

        # ---------------------------------------------
        # Biến động chậm theo tuần
        # ---------------------------------------------

        weekly_cycle = math.sin(
            2.0
            *
            math.pi
            *
            elapsed_days
            /
            7.0
        )

        # ---------------------------------------------
        # Pollution episode:
        # một số ngày trong tuần ô nhiễm tăng.
        # Đây là synthetic scenario,
        # không phải dữ liệu quan trắc thật.
        # ---------------------------------------------

        day_in_week = (
            elapsed_days
            %
            7.0
        )

        pollution_episode = math.exp(
            -0.5
            *
            (
                (
                    day_in_week
                    -
                    3.5
                )
                /
                1.15
            ) ** 2
        )

        return {
            "hour":
                hour,

            "temperature_cycle":
                temperature_cycle,

            "traffic_cycle":
                traffic_cycle,

            "wind_afternoon":
                wind_afternoon,

            "weekly_cycle":
                weekly_cycle,

            "pollution_episode":
                pollution_episode,
        }

    # =====================================================
    # Environmental target
    # =====================================================

    def _target_value(
        self,
        sensor,
        round_number
    ):

        spatial = (
            self._spatial_fields(
                sensor
            )
        )

        temporal = (
            self._temporal_fields(
                round_number
            )
        )

        S = self.spatial_strength
        P = self.pollution_strength

        industrial = (
            spatial["industrial"]
        )

        traffic = (
            spatial["traffic"]
        )

        urban = (
            spatial["urban"]
        )

        green = (
            spatial["green"]
        )

        water_pollution = (
            spatial["water_pollution"]
        )

        sheltered = (
            spatial["sheltered"]
        )

        temp_cycle = (
            temporal[
                "temperature_cycle"
            ]
        )

        traffic_cycle = (
            temporal[
                "traffic_cycle"
            ]
        )

        wind_cycle = (
            temporal[
                "wind_afternoon"
            ]
        )

        weekly = (
            temporal[
                "weekly_cycle"
            ]
        )

        episode = (
            temporal[
                "pollution_episode"
            ]
        )

        sensor_type = (
            sensor.sensor_type
        )

        # =============================================
        # TEMPERATURE
        # =============================================

        if sensor_type == "temperature":

            value = (
                29.0
                +
                4.8
                *
                temp_cycle

                +
                S
                *
                (
                    3.5
                    *
                    urban

                    +
                    1.8
                    *
                    industrial

                    -
                    2.0
                    *
                    green
                )

                +
                0.8
                *
                weekly
            )

        # =============================================
        # HUMIDITY
        # =============================================

        elif sensor_type == "humidity":

            value = (
                70.0

                -
                10.0
                *
                temp_cycle

                +
                S
                *
                (
                    12.0
                    *
                    green

                    -
                    8.0
                    *
                    urban

                    -
                    4.0
                    *
                    industrial
                )

                -
                2.0
                *
                weekly
            )

        # =============================================
        # PM2.5
        # =============================================

        elif sensor_type == "pm25":

            value = (
                18.0

                +
                P
                *
                S
                *
                (
                    58.0
                    *
                    industrial

                    +
                    38.0
                    *
                    traffic

                    +
                    20.0
                    *
                    traffic_cycle
                    *
                    (
                        0.35
                        +
                        traffic
                    )

                    +
                    28.0
                    *
                    episode
                    *
                    (
                        0.25
                        +
                        industrial
                    )
                )

                -
                8.0
                *
                wind_cycle
            )

        # =============================================
        # WIND
        # =============================================

        elif sensor_type == "wind":

            value = (
                2.0

                +
                2.3
                *
                wind_cycle

                +
                S
                *
                (
                    1.0
                    *
                    green

                    -
                    1.3
                    *
                    sheltered

                    -
                    0.7
                    *
                    urban
                )

                +
                0.4
                *
                weekly
            )

        # =============================================
        # WATER QUALITY
        #
        # Score càng cao càng tốt.
        # =============================================

        elif (
            sensor_type
            ==
            "water_quality"
        ):

            value = (
                88.0

                -
                P
                *
                S
                *
                (
                    46.0
                    *
                    water_pollution

                    +
                    22.0
                    *
                    industrial

                    +
                    8.0
                    *
                    traffic
                )

                +
                4.0
                *
                green

                -
                3.0
                *
                episode
                *
                water_pollution
            )

        else:

            raise ValueError(
                "Unknown sensor type: "
                f"{sensor_type}"
            )

        return float(value)

    # =====================================================
    # Generate measurement
    # =====================================================

    def generate(
        self,
        sensor,
        round_number: int,
        simulation_time_seconds: float = 0.0,
        timestamp: datetime | None = None
    ) -> SensorMeasurement:

        sensor_type = (
            sensor.sensor_type
        )

        target = (
            self._target_value(
                sensor,
                round_number
            )
        )

        sigma = float(
            self.noise.get(
                sensor_type,
                0.5
            )
        )

        node_id = sensor.node_id

        previous = (
            self.node_state.get(
                node_id
            )
        )

        # Process noise:
        # biến động thật của môi trường.
        process_sigma = (
            sigma
            *
            0.35
        )

        # Measurement noise:
        # sai số phép đo của sensor.
        measurement_sigma = (
            sigma
            *
            0.65
        )

        if previous is None:

            latent_state = (
                target
                +
                self.rng.normal(
                    0.0,
                    process_sigma
                )
            )

        else:

            latent_state = (
                self.rho
                *
                previous

                +
                (
                    1.0
                    -
                    self.rho
                )
                *
                target

                +
                self.rng.normal(
                    0.0,
                    process_sigma
                )
            )

        # Lưu trạng thái môi trường thật.
        self.node_state[
            node_id
        ] = latent_state

        # Sensor measurement.
        measured_value = (
            latent_state
            +
            self.rng.normal(
                0.0,
                measurement_sigma
            )
        )

        measured_value = (
            self._clamp(
                sensor_type,
                measured_value
            )
        )

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

            value=(
                measured_value
            ),

            unit=(
                self.UNITS[
                    sensor_type
                ]
            ),

            timestamp=(
                timestamp
            )
        )