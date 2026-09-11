import numpy as np
import pandas as pd


class ZoneHistoryTracker:
    """
    Store historical environmental/ELQI
    snapshots for every zone.
    """

    def __init__(self):

        self.records = []

    def record_snapshot(
        self,
        zone_dataframe: pd.DataFrame,
        round_number: int
    ) -> None:

        if zone_dataframe.empty:
            return

        snapshot = (
            zone_dataframe.copy()
        )

        snapshot[
            "round"
        ] = int(
            round_number
        )

        self.records.extend(
            snapshot.to_dict(
                orient="records"
            )
        )

    def dataframe(
        self
    ) -> pd.DataFrame:

        return pd.DataFrame(
            self.records
        )

    def clear(
        self
    ) -> None:

        self.records = []


def _calculate_zone_slope(
    zone_history: pd.DataFrame
) -> float:
    """
    Return ELQI trend in points per 100 rounds.
    """

    valid = (
        zone_history[
            zone_history[
                "elqi"
            ].notna()
        ]
        .copy()
    )

    if len(valid) < 2:

        return float(
            "nan"
        )

    x = (
        valid[
            "round"
        ]
        .to_numpy(
            dtype=float
        )
    )

    y = (
        valid[
            "elqi"
        ]
        .to_numpy(
            dtype=float
        )
    )

    slope = np.polyfit(
        x,
        y,
        1
    )[0]

    return float(
        slope * 100
    )


def classify_degradation(
    delta_elqi: float,
    confidence: float,
    config: dict
) -> str:

    degradation = (
        config[
            "environment"
        ][
            "degradation"
        ]
    )

    minimum_confidence = float(
        degradation[
            "minimum_confidence"
        ]
    )

    if (
        confidence
        <
        minimum_confidence
    ):

        return (
            "Độ tin cậy thấp"
        )

    if np.isnan(
        delta_elqi
    ):

        return (
            "Không đủ dữ liệu"
        )

    improvement_threshold = float(
        degradation[
            "improvement_threshold"
        ]
    )

    stable_tolerance = float(
        degradation[
            "stable_tolerance"
        ]
    )

    significant_threshold = float(
        degradation[
            "significant_decline_threshold"
        ]
    )

    severe_threshold = float(
        degradation[
            "severe_decline_threshold"
        ]
    )

    if (
        delta_elqi
        >=
        improvement_threshold
    ):

        return "Cải thiện"

    if (
        delta_elqi
        >=
        -stable_tolerance
    ):

        return "Ổn định"

    if (
        delta_elqi
        >
        significant_threshold
    ):

        return "Suy giảm nhẹ"

    if (
        delta_elqi
        >
        severe_threshold
    ):

        return (
            "Suy giảm đáng kể"
        )

    return (
        "Suy giảm nghiêm trọng"
    )


def calculate_zone_degradation(
    history_dataframe: pd.DataFrame,
    config: dict,
    current_round: int | None = None
) -> pd.DataFrame:
    """
    Compare current ELQI with approximately
    lookback_rounds in the past.
    """

    if history_dataframe.empty:

        return pd.DataFrame()

    history = (
        history_dataframe.copy()
    )

    available_rounds = sorted(
        history[
            "round"
        ].unique()
    )

    if not available_rounds:

        return pd.DataFrame()

    if current_round is None:

        latest_round = int(
            max(
                available_rounds
            )
        )

    else:

        valid_rounds = [
            round_number
            for round_number
            in available_rounds
            if round_number
            <= current_round
        ]

        if not valid_rounds:

            return pd.DataFrame()

        latest_round = int(
            max(
                valid_rounds
            )
        )

    lookback_rounds = int(
        config[
            "environment"
        ][
            "degradation"
        ][
            "lookback_rounds"
        ]
    )

    target_round = (
        latest_round
        -
        lookback_rounds
    )

    baseline_candidates = [
        round_number
        for round_number
        in available_rounds
        if round_number
        <= target_round
    ]

    full_lookback = bool(
        baseline_candidates
    )

    if baseline_candidates:

        baseline_round = int(
            max(
                baseline_candidates
            )
        )

    else:

        baseline_round = int(
            min(
                available_rounds
            )
        )

    current_snapshot = (
        history[
            history[
                "round"
            ]
            ==
            latest_round
        ]
        .copy()
    )

    baseline_snapshot = (
        history[
            history[
                "round"
            ]
            ==
            baseline_round
        ]
        .copy()
    )

    if (
        current_snapshot.empty
        or
        baseline_snapshot.empty
    ):

        return pd.DataFrame()

    keep_current = [
        "zone_id",
        "row",
        "column",
        "center_x",
        "center_y",
        "elqi",
        "rating",
        "confidence"
    ]

    keep_baseline = [
        "zone_id",
        "elqi",
        "confidence"
    ]

    current_snapshot = (
        current_snapshot[
            keep_current
        ]
        .rename(
            columns={
                "elqi":
                    "current_elqi",

                "rating":
                    "current_rating",

                "confidence":
                    "current_confidence"
            }
        )
    )

    baseline_snapshot = (
        baseline_snapshot[
            keep_baseline
        ]
        .rename(
            columns={
                "elqi":
                    "baseline_elqi",

                "confidence":
                    "baseline_confidence"
            }
        )
    )

    result = (
        current_snapshot.merge(
            baseline_snapshot,

            on="zone_id",

            how="left"
        )
    )

    result[
        "delta_elqi"
    ] = (
        result[
            "current_elqi"
        ]
        -
        result[
            "baseline_elqi"
        ]
    )

    result[
        "comparison_confidence"
    ] = (
        result[
            [
                "current_confidence",
                "baseline_confidence"
            ]
        ]
        .min(
            axis=1
        )
    )

    result[
        "latest_round"
    ] = latest_round

    result[
        "baseline_round"
    ] = baseline_round

    result[
        "history_span_rounds"
    ] = (
        latest_round
        -
        baseline_round
    )

    result[
        "full_lookback"
    ] = full_lookback

    trend_values = {}

    trend_history = (
        history[
            (
                history[
                    "round"
                ]
                >=
                baseline_round
            )
            &
            (
                history[
                    "round"
                ]
                <=
                latest_round
            )
        ]
    )

    for (
        zone_id,
        zone_history
    ) in trend_history.groupby(
        "zone_id"
    ):

        trend_values[
            zone_id
        ] = (
            _calculate_zone_slope(
                zone_history
            )
        )

    result[
        "trend_per_100_rounds"
    ] = (
        result[
            "zone_id"
        ]
        .map(
            trend_values
        )
    )

    result[
        "degradation_status"
    ] = [
        classify_degradation(
            delta_elqi=delta,

            confidence=confidence,

            config=config
        )

        for delta, confidence
        in zip(
            result[
                "delta_elqi"
            ],

            result[
                "comparison_confidence"
            ]
        )
    ]

    return result