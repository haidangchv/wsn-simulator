import math

import numpy as np


def clamp_score(
    score: float
) -> float:

    return max(
        0.0,
        min(
            100.0,
            float(score)
        )
    )


def optimal_range_score(
    value: float,
    hard_min: float,
    ideal_min: float,
    ideal_max: float,
    hard_max: float
) -> float:
    """
    100 points inside ideal range.

    Score decreases linearly toward zero
    when approaching hard limits.
    """

    if (
        value <= hard_min
        or
        value >= hard_max
    ):
        return 0.0

    if (
        ideal_min
        <= value
        <= ideal_max
    ):
        return 100.0

    if value < ideal_min:

        score = (
            100.0
            *
            (
                value
                -
                hard_min
            )
            /
            (
                ideal_min
                -
                hard_min
            )
        )

        return clamp_score(
            score
        )

    score = (
        100.0
        *
        (
            hard_max
            -
            value
        )
        /
        (
            hard_max
            -
            ideal_max
        )
    )

    return clamp_score(
        score
    )


def breakpoint_score(
    value: float,
    breakpoints
) -> float:

    points = sorted(
        breakpoints,
        key=lambda pair:
            pair[0]
    )

    x = [
        float(pair[0])
        for pair in points
    ]

    y = [
        float(pair[1])
        for pair in points
    ]

    score = np.interp(
        value,
        x,
        y,
        left=y[0],
        right=y[-1]
    )

    return clamp_score(
        score
    )


def score_indicator(
    sensor_type: str,
    value: float,
    config: dict
) -> float:

    if (
        value is None
        or
        math.isnan(
            float(value)
        )
    ):
        return float(
            "nan"
        )

    scoring = (
        config[
            "environment"
        ][
            "living_quality"
        ][
            "scoring"
        ][
            sensor_type
        ]
    )

    method = scoring[
        "method"
    ]

    if (
        method
        == "optimal_range"
    ):

        return (
            optimal_range_score(
                value=float(value),

                hard_min=float(
                    scoring[
                        "hard_min"
                    ]
                ),

                ideal_min=float(
                    scoring[
                        "ideal_min"
                    ]
                ),

                ideal_max=float(
                    scoring[
                        "ideal_max"
                    ]
                ),

                hard_max=float(
                    scoring[
                        "hard_max"
                    ]
                )
            )
        )

    if (
        method
        == "breakpoints"
    ):

        return (
            breakpoint_score(
                value=float(value),

                breakpoints=(
                    scoring[
                        "breakpoints"
                    ]
                )
            )
        )

    if (
        method
        == "direct_score"
    ):

        return clamp_score(
            value
        )

    raise ValueError(
        f"Unknown scoring method: "
        f"{method}"
    )