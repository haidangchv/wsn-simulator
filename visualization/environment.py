import numpy as np
import plotly.graph_objects as go

from environment.interpolation import (
    create_idw_grid
)

def create_elqi_zone_map(
    zone_dataframe,
    config: dict,
    sink=None
):

    if zone_dataframe.empty:
        return None

    rows = sorted(
        zone_dataframe[
            "row"
        ].unique()
    )

    columns = sorted(
        zone_dataframe[
            "column"
        ].unique()
    )

    row_lookup = {
        value: index
        for index, value
        in enumerate(rows)
    }

    column_lookup = {
        value: index
        for index, value
        in enumerate(columns)
    }

    shape = (
        len(rows),
        len(columns)
    )

    z = np.full(
        shape,
        np.nan
    )

    zone_names = np.empty(
        shape,
        dtype=object
    )

    ratings = np.empty(
        shape,
        dtype=object
    )

    confidence = np.zeros(
        shape
    )

    x_centers = (
        zone_dataframe
        .groupby(
            "column"
        )[
            "center_x"
        ]
        .first()
        .sort_index()
        .to_numpy()
    )

    y_centers = (
        zone_dataframe
        .groupby(
            "row"
        )[
            "center_y"
        ]
        .first()
        .sort_index()
        .to_numpy()
    )

    for _, zone in (
        zone_dataframe.iterrows()
    ):

        row_index = row_lookup[
            zone[
                "row"
            ]
        ]

        column_index = (
            column_lookup[
                zone[
                    "column"
                ]
            ]
        )

        z[
            row_index,
            column_index
        ] = zone[
            "elqi"
        ]

        zone_names[
            row_index,
            column_index
        ] = zone[
            "zone_id"
        ]

        ratings[
            row_index,
            column_index
        ] = zone[
            "rating"
        ]

        confidence[
            row_index,
            column_index
        ] = zone[
            "confidence"
        ]

    customdata = np.empty(
        (
            len(rows),
            len(columns),
            3
        ),
        dtype=object
    )

    customdata[
        :,
        :,
        0
    ] = zone_names

    customdata[
        :,
        :,
        1
    ] = ratings

    customdata[
        :,
        :,
        2
    ] = confidence

    fig = go.Figure()

    fig.add_trace(
        go.Heatmap(
            x=x_centers,
            y=y_centers,

            z=z,

            zmin=0,
            zmax=100,

            colorscale="RdYlGn",

            colorbar=dict(
                title="ELQI"
            ),

            customdata=customdata,

            hovertemplate=(
                "Zone: %{customdata[0]}"
                "<br>ELQI: %{z:.1f}"
                "<br>Rating: %{customdata[1]}"
                "<br>Confidence: "
                "%{customdata[2]:.0%}"
                "<extra></extra>"
            )
        )
    )

    low_confidence = (
        zone_dataframe[
            zone_dataframe[
                "low_confidence"
            ]
        ]
    )

    if not low_confidence.empty:

        fig.add_trace(
            go.Scatter(
                x=(
                    low_confidence[
                        "center_x"
                    ]
                ),

                y=(
                    low_confidence[
                        "center_y"
                    ]
                ),

                mode="text",

                text=[
                    "⚠"
                    for _ in range(
                        len(
                            low_confidence
                        )
                    )
                ],

                textfont=dict(
                    size=14
                ),

                hoverinfo="skip",

                name="Low confidence"
            )
        )

    if sink is not None:

        fig.add_trace(
            go.Scatter(
                x=[sink.x],
                y=[sink.y],

                mode="markers+text",

                marker=dict(
                    symbol="star",
                    size=18
                ),

                text=["SINK"],

                textposition="top center",

                name="Sink"
            )
        )

    width = float(
        config[
            "network"
        ][
            "width_m"
        ]
    )

    height = float(
        config[
            "network"
        ][
            "height_m"
        ]
    )

    fig.update_layout(
        title=(
            "Environmental Living "
            "Quality Index Map"
        ),

        xaxis_title="X (m)",
        yaxis_title="Y (m)",

        height=700
    )

    fig.update_xaxes(
        range=[
            0,
            width
        ]
    )

    fig.update_yaxes(
        range=[
            0,
            height
        ],

        scaleanchor="x",
        scaleratio=1
    )

    return fig

def create_confidence_map(
    zone_dataframe,
    config: dict
):

    if zone_dataframe.empty:
        return None

    pivot = (
        zone_dataframe.pivot(
            index="row",
            columns="column",
            values="confidence"
        )
    )

    x_centers = (
        zone_dataframe
        .groupby(
            "column"
        )[
            "center_x"
        ]
        .first()
        .sort_index()
        .to_numpy()
    )

    y_centers = (
        zone_dataframe
        .groupby(
            "row"
        )[
            "center_y"
        ]
        .first()
        .sort_index()
        .to_numpy()
    )

    fig = go.Figure(
        go.Heatmap(
            x=x_centers,

            y=y_centers,

            z=pivot.values,

            zmin=0,
            zmax=1,

            colorscale="Blues",

            colorbar=dict(
                title="Confidence"
            ),

            hovertemplate=(
                "X: %{x:.0f} m"
                "<br>Y: %{y:.0f} m"
                "<br>Confidence: %{z:.0%}"
                "<extra></extra>"
            )
        )
    )

    fig.update_layout(
        title=(
            "Environmental Data Confidence"
        ),

        height=650,

        xaxis_title="X (m)",
        yaxis_title="Y (m)"
    )

    fig.update_yaxes(
        scaleanchor="x",
        scaleratio=1
    )

    return fig

def create_degradation_map(
    degradation_dataframe,
    config: dict,
    sink=None
):

    if degradation_dataframe.empty:
        return None

    rows = sorted(
        degradation_dataframe[
            "row"
        ].unique()
    )

    columns = sorted(
        degradation_dataframe[
            "column"
        ].unique()
    )

    row_lookup = {
        value: index
        for index, value
        in enumerate(rows)
    }

    column_lookup = {
        value: index
        for index, value
        in enumerate(columns)
    }

    shape = (
        len(rows),
        len(columns)
    )

    z = np.full(
        shape,
        np.nan
    )

    customdata = np.empty(
        (
            len(rows),
            len(columns),
            7
        ),
        dtype=object
    )

    for _, zone in (
        degradation_dataframe.iterrows()
    ):

        r = row_lookup[
            zone["row"]
        ]

        c = column_lookup[
            zone["column"]
        ]

        z[
            r,
            c
        ] = zone[
            "delta_elqi"
        ]

        customdata[
            r,
            c,
            0
        ] = zone[
            "zone_id"
        ]

        customdata[
            r,
            c,
            1
        ] = zone[
            "baseline_elqi"
        ]

        customdata[
            r,
            c,
            2
        ] = zone[
            "current_elqi"
        ]

        customdata[
            r,
            c,
            3
        ] = zone[
            "degradation_status"
        ]

        customdata[
            r,
            c,
            4
        ] = zone[
            "comparison_confidence"
        ]

        customdata[
            r,
            c,
            5
        ] = zone[
            "baseline_round"
        ]

        customdata[
            r,
            c,
            6
        ] = zone[
            "latest_round"
        ]

    finite_values = (
        degradation_dataframe[
            "delta_elqi"
        ]
        .dropna()
        .abs()
    )

    if finite_values.empty:

        max_abs = 10.0

    else:

        max_abs = max(
            5.0,

            float(
                finite_values.max()
            )
        )

    x_centers = (
        degradation_dataframe
        .groupby(
            "column"
        )[
            "center_x"
        ]
        .first()
        .sort_index()
        .to_numpy()
    )

    y_centers = (
        degradation_dataframe
        .groupby(
            "row"
        )[
            "center_y"
        ]
        .first()
        .sort_index()
        .to_numpy()
    )

    fig = go.Figure()

    fig.add_trace(
        go.Heatmap(
            x=x_centers,

            y=y_centers,

            z=z,

            zmin=-max_abs,

            zmax=max_abs,

            zmid=0,

            colorscale="RdYlGn",

            colorbar=dict(
                title="Δ ELQI"
            ),

            customdata=(
                customdata
            ),

            hovertemplate=(
                "Zone: %{customdata[0]}"
                "<br>Previous ELQI: "
                "%{customdata[1]:.1f}"
                "<br>Current ELQI: "
                "%{customdata[2]:.1f}"
                "<br>Δ ELQI: %{z:.1f}"
                "<br>Status: "
                "%{customdata[3]}"
                "<br>Confidence: "
                "%{customdata[4]:.0%}"
                "<br>Rounds: "
                "%{customdata[5]}"
                " → %{customdata[6]}"
                "<extra></extra>"
            )
        )
    )

    unreliable = (
        degradation_dataframe[
            degradation_dataframe[
                "degradation_status"
            ]
            ==
            "Độ tin cậy thấp"
        ]
    )

    if not unreliable.empty:

        fig.add_trace(
            go.Scatter(
                x=(
                    unreliable[
                        "center_x"
                    ]
                ),

                y=(
                    unreliable[
                        "center_y"
                    ]
                ),

                mode="text",

                text=[
                    "⚠"
                    for _
                    in range(
                        len(
                            unreliable
                        )
                    )
                ],

                hoverinfo="skip",

                name="Low confidence"
            )
        )

    if sink is not None:

        fig.add_trace(
            go.Scatter(
                x=[sink.x],

                y=[sink.y],

                mode="markers+text",

                marker=dict(
                    symbol="star",
                    size=18
                ),

                text=["SINK"],

                textposition=(
                    "top center"
                ),

                name="Sink"
            )
        )

    width = float(
        config[
            "network"
        ][
            "width_m"
        ]
    )

    height = float(
        config[
            "network"
        ][
            "height_m"
        ]
    )

    fig.update_layout(
        title=(
            "Environmental Quality "
            "Degradation Map"
        ),

        xaxis_title="X (m)",

        yaxis_title="Y (m)",

        height=700
    )

    fig.update_xaxes(
        range=[
            0,
            width
        ]
    )

    fig.update_yaxes(
        range=[
            0,
            height
        ],

        scaleanchor="x",

        scaleratio=1
    )

    return fig

def create_indicator_heatmap(
    snapshot,
    sensor_type: str,
    config: dict,
    sink=None
):

    if snapshot.empty:
        return None

    width = float(
        config["network"][
            "width_m"
        ]
    )

    height = float(
        config["network"][
            "height_m"
        ]
    )

    interpolation = (
        config[
            "environment"
        ][
            "interpolation"
        ]
    )

    grid_x, grid_y, grid_z = (
        create_idw_grid(
            dataframe=snapshot,

            width_m=width,

            height_m=height,

            resolution=int(
                interpolation[
                    "grid_resolution"
                ]
            ),

            power=float(
                interpolation[
                    "power"
                ]
            )
        )
    )

    unit = (
        snapshot[
            "unit"
        ].iloc[0]
    )

    fig = go.Figure()

    fig.add_trace(
        go.Heatmap(
            x=grid_x,
            y=grid_y,
            z=grid_z,

            colorscale="Viridis",

            colorbar=dict(
                title=unit
            ),

            hovertemplate=(
                "X: %{x:.0f} m"
                "<br>Y: %{y:.0f} m"
                "<br>Value: %{z:.2f}"
                "<extra></extra>"
            )
        )
    )

    # Original sensor measurements
    fig.add_trace(
        go.Scatter(
            x=snapshot["x"],
            y=snapshot["y"],

            mode="markers",

            marker=dict(
                symbol="circle-open",
                size=7
            ),

            customdata=np.column_stack([
                snapshot[
                    "source_id"
                ],

                snapshot[
                    "value"
                ]
            ]),

            hovertemplate=(
                "Sensor %{customdata[0]}"
                "<br>Measured: "
                "%{customdata[1]:.2f}"
                "<extra></extra>"
            ),

            name="Sensors"
        )
    )

    if sink is not None:

        fig.add_trace(
            go.Scatter(
                x=[sink.x],
                y=[sink.y],

                mode="markers+text",

                marker=dict(
                    symbol="star",
                    size=18
                ),

                text=["SINK"],

                textposition=(
                    "top center"
                ),

                name="Sink"
            )
        )

    fig.update_layout(
        title=(
            f"{sensor_type} Heatmap"
        ),

        xaxis_title="X (m)",
        yaxis_title="Y (m)",

        height=650,

        margin=dict(
            l=20,
            r=20,
            t=60,
            b=20
        )
    )

    fig.update_xaxes(
        range=[
            0,
            width
        ]
    )

    fig.update_yaxes(
        range=[
            0,
            height
        ],

        scaleanchor="x",

        scaleratio=1
    )

    return fig