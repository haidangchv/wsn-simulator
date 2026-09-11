import pandas as pd


def build_zone_alerts(
    degradation_dataframe: pd.DataFrame,
    config: dict
) -> pd.DataFrame:

    if degradation_dataframe.empty:

        return pd.DataFrame()

    alert_config = (
        config[
            "environment"
        ][
            "alerts"
        ]
    )

    warning_elqi = float(
        alert_config[
            "warning_elqi_below"
        ]
    )

    critical_elqi = float(
        alert_config[
            "critical_elqi_below"
        ]
    )

    decline_threshold = float(
        alert_config[
            "significant_decline_below"
        ]
    )

    minimum_confidence = float(
        config[
            "environment"
        ][
            "degradation"
        ][
            "minimum_confidence"
        ]
    )

    alerts = []

    for _, zone in (
        degradation_dataframe.iterrows()
    ):

        confidence = float(
            zone[
                "comparison_confidence"
            ]
        )

        if (
            confidence
            <
            minimum_confidence
        ):

            alerts.append({

                "zone_id":
                    zone[
                        "zone_id"
                    ],

                "severity":
                    "DATA",

                "message":
                    (
                        "Độ tin cậy dữ liệu thấp"
                    ),

                "elqi":
                    zone[
                        "current_elqi"
                    ],

                "delta_elqi":
                    zone[
                        "delta_elqi"
                    ],

                "confidence":
                    confidence
            })

            continue

        current_elqi = float(
            zone[
                "current_elqi"
            ]
        )

        delta = float(
            zone[
                "delta_elqi"
            ]
        )

        reasons = []

        severity = None

        if (
            current_elqi
            <
            critical_elqi
        ):

            severity = "CRITICAL"

            reasons.append(
                "Chất lượng môi trường rất kém"
            )

        elif (
            current_elqi
            <
            warning_elqi
        ):

            severity = "WARNING"

            reasons.append(
                "Chất lượng môi trường thấp"
            )

        if (
            delta
            <=
            decline_threshold
        ):

            if severity is None:

                severity = "WARNING"

            reasons.append(
                (
                    "ELQI suy giảm "
                    f"{abs(delta):.1f} điểm"
                )
            )

        if severity is None:
            continue

        alerts.append({

            "zone_id":
                zone[
                    "zone_id"
                ],

            "severity":
                severity,

            "message":
                "; ".join(
                    reasons
                ),

            "elqi":
                current_elqi,

            "delta_elqi":
                delta,

            "confidence":
                confidence
        })

    if not alerts:

        return pd.DataFrame()

    severity_order = {
        "CRITICAL": 0,
        "WARNING": 1,
        "DATA": 2
    }

    dataframe = (
        pd.DataFrame(
            alerts
        )
    )

    dataframe[
        "_priority"
    ] = (
        dataframe[
            "severity"
        ]
        .map(
            severity_order
        )
    )

    return (
        dataframe
        .sort_values(
            [
                "_priority",
                "elqi"
            ]
        )
        .drop(
            columns=[
                "_priority"
            ]
        )
        .reset_index(
            drop=True
        )
    )