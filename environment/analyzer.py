import numpy as np
import pandas as pd

from environment.interpolation import (
    idw_estimate_points
)

from environment.living_quality import (
    SENSOR_TYPES,
    calculate_elqi,
    classify_elqi
)

from environment.scoring import (
    score_indicator
)

from environment.zones import (
    create_zones
)


class EnvironmentalAnalyzer:

    def __init__(
        self,
        config: dict
    ):

        self.config = config

        environment = (
            config[
                "environment"
            ]
        )

        self.max_age_rounds = int(
            environment[
                "freshness_max_rounds"
            ]
        )

        self.power = float(
            environment[
                "interpolation"
            ][
                "power"
            ]
        )

        confidence = (
            environment[
                "confidence"
            ]
        )

        self.support_radius_m = float(
            confidence[
                "support_radius_m"
            ]
        )

        self.low_confidence_threshold = (
            float(
                confidence[
                    "low_confidence_threshold"
                ]
            )
        )

    def latest_sensor_snapshot(
        self,
        collector,
        current_round: int,
        sensor_type: str
    ) -> pd.DataFrame:
        """
        Use the latest received value from each
        sensor, provided it is not stale.
        """

        dataframe = (
            collector.received_dataframe()
        )

        if dataframe.empty:
            return dataframe

        dataframe = (
            dataframe[
                dataframe[
                    "sensor_type"
                ]
                ==
                sensor_type
            ]
            .copy()
        )

        if dataframe.empty:
            return dataframe

        minimum_round = (
            current_round
            -
            self.max_age_rounds
        )

        dataframe = (
            dataframe[
                dataframe[
                    "round"
                ]
                >=
                minimum_round
            ]
        )

        if dataframe.empty:
            return dataframe

        return (
            dataframe
            .sort_values(
                "round"
            )
            .groupby(
                "source_id",
                as_index=False
            )
            .tail(1)
            .reset_index(
                drop=True
            )
        )

    def _delivery_ratio(
        self,
        collector,
        current_round: int,
        sensor_type: str
    ) -> float:

        generated = pd.DataFrame(
            collector.generated_records
        )

        received = pd.DataFrame(
            collector.received_records
        )

        if generated.empty:
            return 0.0

        minimum_round = (
            current_round
            -
            self.max_age_rounds
        )

        generated = (
            generated[
                (
                    generated[
                        "sensor_type"
                    ]
                    ==
                    sensor_type
                )
                &
                (
                    generated[
                        "round"
                    ]
                    >=
                    minimum_round
                )
            ]
        )

        if generated.empty:
            return 0.0

        if received.empty:
            return 0.0

        received = (
            received[
                (
                    received[
                        "sensor_type"
                    ]
                    ==
                    sensor_type
                )
                &
                (
                    received[
                        "round"
                    ]
                    >=
                    minimum_round
                )
            ]
        )

        return min(
            1.0,

            len(received)
            /
            len(generated)
        )

    @staticmethod
    def _nearest_support(
        dataframe: pd.DataFrame,
        target_x,
        target_y,
        current_round: int
    ):
        """
        Return nearest sensor distance and age
        for each target location.
        """

        target_x = np.asarray(
            target_x,
            dtype=float
        )

        target_y = np.asarray(
            target_y,
            dtype=float
        )

        if dataframe.empty:

            return (
                np.full(
                    target_x.shape,
                    np.inf
                ),

                np.full(
                    target_x.shape,
                    np.inf
                )
            )

        point_x = (
            dataframe["x"]
            .to_numpy(
                dtype=float
            )
        )

        point_y = (
            dataframe["y"]
            .to_numpy(
                dtype=float
            )
        )

        rounds = (
            dataframe["round"]
            .to_numpy(
                dtype=float
            )
        )

        dx = (
            target_x[:, None]
            -
            point_x[None, :]
        )

        dy = (
            target_y[:, None]
            -
            point_y[None, :]
        )

        distances = np.sqrt(
            dx ** 2
            +
            dy ** 2
        )

        nearest_index = (
            np.argmin(
                distances,
                axis=1
            )
        )

        row_index = np.arange(
            len(target_x)
        )

        nearest_distance = (
            distances[
                row_index,
                nearest_index
            ]
        )

        nearest_round = (
            rounds[
                nearest_index
            ]
        )

        age = np.maximum(
            0,
            current_round
            -
            nearest_round
        )

        return (
            nearest_distance,
            age
        )

    def build_zone_snapshot(
        self,
        collector,
        current_round: int
    ) -> pd.DataFrame:

        zones = create_zones(
            self.config
        )

        target_x = (
            zones[
                "center_x"
            ]
            .to_numpy()
        )

        target_y = (
            zones[
                "center_y"
            ]
            .to_numpy()
        )

        confidence_columns = []

        for sensor_type in (
            SENSOR_TYPES
        ):

            snapshot = (
                self.latest_sensor_snapshot(
                    collector=collector,

                    current_round=(
                        current_round
                    ),

                    sensor_type=(
                        sensor_type
                    )
                )
            )

            value_column = (
                sensor_type
            )

            score_column = (
                f"{sensor_type}_score"
            )

            confidence_column = (
                f"{sensor_type}_confidence"
            )

            confidence_columns.append(
                confidence_column
            )

            if snapshot.empty:

                zones[
                    value_column
                ] = np.nan

                zones[
                    score_column
                ] = np.nan

                zones[
                    confidence_column
                ] = 0.0

                continue

            estimates = (
                idw_estimate_points(
                    dataframe=snapshot,

                    target_x=target_x,

                    target_y=target_y,

                    power=self.power
                )
            )

            zones[
                value_column
            ] = estimates

            zones[
                score_column
            ] = [
                score_indicator(
                    sensor_type,
                    value,
                    self.config
                )
                for value in estimates
            ]

            (
                nearest_distance,
                age
            ) = self._nearest_support(
                dataframe=snapshot,

                target_x=target_x,

                target_y=target_y,

                current_round=(
                    current_round
                )
            )

            spatial_confidence = (
                np.clip(
                    1.0
                    -
                    (
                        nearest_distance
                        /
                        self.support_radius_m
                    ),

                    0.0,
                    1.0
                )
            )

            freshness_confidence = (
                np.clip(
                    1.0
                    -
                    (
                        age
                        /
                        (
                            self.max_age_rounds
                            +
                            1
                        )
                    ),

                    0.0,
                    1.0
                )
            )

            delivery_ratio = (
                self._delivery_ratio(
                    collector=collector,

                    current_round=(
                        current_round
                    ),

                    sensor_type=(
                        sensor_type
                    )
                )
            )

            zones[
                confidence_column
            ] = (
                0.50
                * spatial_confidence
                +
                0.25
                * freshness_confidence
                +
                0.25
                * delivery_ratio
            )

        available_columns = [
            sensor_type
            for sensor_type
            in SENSOR_TYPES
        ]

        zones[
            "data_types_available"
        ] = (
            zones[
                available_columns
            ]
            .notna()
            .sum(
                axis=1
            )
        )

        coverage_ratio = (
            zones[
                "data_types_available"
            ]
            /
            len(
                SENSOR_TYPES
            )
        )

        zones[
            "confidence"
        ] = (
            zones[
                confidence_columns
            ]
            .mean(
                axis=1
            )
            *
            coverage_ratio
        )

        elqi_values = []
        ratings = []

        for _, row in (
            zones.iterrows()
        ):

            indicator_scores = {
                sensor_type:
                    row[
                        f"{sensor_type}_score"
                    ]

                for sensor_type
                in SENSOR_TYPES
            }

            elqi = calculate_elqi(
                indicator_scores=(
                    indicator_scores
                ),

                config=self.config
            )

            elqi_values.append(
                elqi
            )

            ratings.append(
                classify_elqi(
                    elqi,
                    self.config
                )
            )

        zones[
            "elqi"
        ] = elqi_values

        zones[
            "rating"
        ] = ratings

        zones[
            "low_confidence"
        ] = (
            zones[
                "confidence"
            ]
            <
            self.low_confidence_threshold
        )

        return zones