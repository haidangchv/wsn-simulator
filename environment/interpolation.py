import numpy as np
import pandas as pd


def idw_estimate_points(
    dataframe: pd.DataFrame,
    target_x,
    target_y,
    power: float = 2.0
) -> np.ndarray:
    """
    Estimate values at arbitrary target points
    using Inverse Distance Weighting.
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

        return np.full(
            target_x.shape,
            np.nan
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

    values = (
        dataframe["value"]
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

    epsilon = 1e-9

    weights = (
        1.0
        /
        np.maximum(
            distances,
            epsilon
        ) ** power
    )

    estimates = (
        weights @ values
        /
        weights.sum(
            axis=1
        )
    )

    # Exact sensor location should retain
    # the measured value.
    exact_rows = np.where(
        np.any(
            distances < epsilon,
            axis=1
        )
    )[0]

    for row_index in exact_rows:

        exact_values = values[
            distances[
                row_index
            ]
            <
            epsilon
        ]

        estimates[
            row_index
        ] = exact_values.mean()

    return estimates


def create_idw_grid(
    dataframe: pd.DataFrame,
    width_m: float,
    height_m: float,
    resolution: int = 70,
    power: float = 2.0
):
    """
    Create a regular interpolated grid.
    """

    grid_x = np.linspace(
        0,
        width_m,
        resolution
    )

    grid_y = np.linspace(
        0,
        height_m,
        resolution
    )

    mesh_x, mesh_y = (
        np.meshgrid(
            grid_x,
            grid_y
        )
    )

    estimated = (
        idw_estimate_points(
            dataframe=dataframe,

            target_x=(
                mesh_x.ravel()
            ),

            target_y=(
                mesh_y.ravel()
            ),

            power=power
        )
    )

    grid_z = estimated.reshape(
        mesh_x.shape
    )

    return (
        grid_x,
        grid_y,
        grid_z
    )