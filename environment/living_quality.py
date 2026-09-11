import math

import numpy as np


SENSOR_TYPES = [
    "temperature",
    "humidity",
    "pm25",
    "wind",
    "water_quality"
]


def calculate_elqi(
    indicator_scores: dict,
    config: dict
) -> float:

    quality_config = (
        config[
            "environment"
        ][
            "living_quality"
        ]
    )

    weights = (
        quality_config[
            "weights"
        ]
    )

    minimum_indicators = int(
        quality_config[
            "minimum_indicators_for_elqi"
        ]
    )

    available = []

    for sensor_type in (
        SENSOR_TYPES
    ):

        score = (
            indicator_scores.get(
                sensor_type
            )
        )

        if score is None:
            continue

        if math.isnan(
            float(score)
        ):
            continue

        available.append(
            sensor_type
        )

    if (
        len(available)
        <
        minimum_indicators
    ):

        return float(
            "nan"
        )

    available_weight = sum(
        float(
            weights[
                sensor_type
            ]
        )
        for sensor_type
        in available
    )

    if available_weight <= 0:
        return float(
            "nan"
        )

    weighted_score = sum(
        float(
            indicator_scores[
                sensor_type
            ]
        )
        *
        float(
            weights[
                sensor_type
            ]
        )

        for sensor_type
        in available
    )

    return (
        weighted_score
        /
        available_weight
    )


def classify_elqi(
    score: float,
    config: dict
) -> str:

    if (
        score is None
        or
        np.isnan(
            score
        )
    ):

        return (
            "Không đủ dữ liệu"
        )

    ratings = (
        config[
            "environment"
        ][
            "living_quality"
        ][
            "ratings"
        ]
    )

    ordered = sorted(
        ratings.values(),

        key=lambda item:
            float(
                item[
                    "min_score"
                ]
            ),

        reverse=True
    )

    for rating in ordered:

        if (
            score
            >=
            float(
                rating[
                    "min_score"
                ]
            )
        ):

            return str(
                rating[
                    "label"
                ]
            )

    return (
        "Không xác định"
    )