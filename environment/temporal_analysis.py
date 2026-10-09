import pandas as pd


def prepare_time_dataframe(
    dataframe: pd.DataFrame
) -> pd.DataFrame:
    """
    Ensure the timestamp column is parsed into pandas datetime.
    """
    if dataframe is None or dataframe.empty:
        return pd.DataFrame()

    df = dataframe.copy()

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(
            df["timestamp"]
        )
    elif "round" in df.columns:
        # Fallback if timestamp column is missing
        base_time = pd.Timestamp("2026-01-01 00:00:00")
        df["timestamp"] = df["round"].apply(
            lambda r: base_time + pd.Timedelta(hours=max(int(r) - 1, 0))
        )

    return df


def hourly_statistics(
    dataframe: pd.DataFrame
) -> pd.DataFrame:
    """
    Compute hourly aggregated metrics (mean, min, max, std, count) per sensor_type.
    """
    df = prepare_time_dataframe(dataframe)

    if df.empty or "value" not in df.columns:
        return pd.DataFrame()

    return (
        df.groupby(
            [
                pd.Grouper(
                    key="timestamp",
                    freq="h"
                ),
                "sensor_type"
            ]
        )["value"]
        .agg(
            [
                "mean",
                "min",
                "max",
                "std",
                "count"
            ]
        )
        .reset_index()
    )


def daily_statistics(
    dataframe: pd.DataFrame
) -> pd.DataFrame:
    """
    Compute daily aggregated metrics (mean, min, max, std, count) per sensor_type.
    """
    df = prepare_time_dataframe(dataframe)

    if df.empty or "value" not in df.columns:
        return pd.DataFrame()

    return (
        df.groupby(
            [
                pd.Grouper(
                    key="timestamp",
                    freq="D"
                ),
                "sensor_type"
            ]
        )["value"]
        .agg(
            [
                "mean",
                "min",
                "max",
                "std",
                "count"
            ]
        )
        .reset_index()
    )


def weekly_statistics(
    dataframe: pd.DataFrame
) -> pd.DataFrame:
    """
    Compute weekly aggregated metrics (mean, min, max, std, count) per sensor_type.
    """
    df = prepare_time_dataframe(dataframe)

    if df.empty or "value" not in df.columns:
        return pd.DataFrame()

    return (
        df.groupby(
            [
                pd.Grouper(
                    key="timestamp",
                    freq="W"
                ),
                "sensor_type"
            ]
        )["value"]
        .agg(
            [
                "mean",
                "min",
                "max",
                "std",
                "count"
            ]
        )
        .reset_index()
    )


def monthly_statistics(
    dataframe: pd.DataFrame
) -> pd.DataFrame:
    """
    Compute monthly aggregated metrics (mean, min, max, std, count) per sensor_type using real calendar months.
    """
    df = prepare_time_dataframe(dataframe)

    if df.empty or "value" not in df.columns:
        return pd.DataFrame()

    df["month"] = (
        df["timestamp"]
        .dt
        .to_period("M")
        .astype(str)
    )

    return (
        df.groupby(
            [
                "month",
                "sensor_type"
            ]
        )["value"]
        .agg(
            [
                "mean",
                "min",
                "max",
                "std",
                "count"
            ]
        )
        .reset_index()
    )
