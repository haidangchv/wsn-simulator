import plotly.graph_objects as go


def create_network_figure(
    network,
    route=None,
    show_edges=True
):
    """
    Create an interactive Plotly visualization
    for the WSN topology.
    """

    sensors = network.sensors
    sink = network.sink
    graph = network.graph

    sensor_map = {
        sensor.node_id: sensor
        for sensor in sensors
    }

    fig = go.Figure()

    # --------------------------------
    # Neighbor links
    # --------------------------------

    if show_edges:

        edge_x = []
        edge_y = []

        for node_a, node_b in graph.edges():

            if node_a == sink.node_id:
                x1, y1 = sink.x, sink.y
            else:
                sensor_a = sensor_map[node_a]
                x1, y1 = sensor_a.x, sensor_a.y

            if node_b == sink.node_id:
                x2, y2 = sink.x, sink.y
            else:
                sensor_b = sensor_map[node_b]
                x2, y2 = sensor_b.x, sensor_b.y

            edge_x.extend(
                [x1, x2, None]
            )

            edge_y.extend(
                [y1, y2, None]
            )

        fig.add_trace(
            go.Scattergl(
                x=edge_x,
                y=edge_y,
                mode="lines",
                line=dict(
                    width=0.5,
                    color="rgba(120,120,120,0.18)"
                ),
                hoverinfo="skip",
                name="Communication links"
            )
        )

    # --------------------------------
    # Sensor nodes by state
    # --------------------------------

    state_settings = {
        "ALIVE": {
            "color": "#2ca02c",
            "size": 7
        },
        "LOW_ENERGY": {
            "color": "#ffb000",
            "size": 8
        },
        "DEAD": {
            "color": "#d62728",
            "size": 7
        }
    }

    for state, settings in (
        state_settings.items()
    ):

        group = [
            sensor
            for sensor in sensors
            if sensor.state == state
        ]

        if not group:
            continue

        fig.add_trace(
            go.Scattergl(
                x=[
                    sensor.x
                    for sensor in group
                ],
                y=[
                    sensor.y
                    for sensor in group
                ],
                mode="markers",

                marker=dict(
                    size=settings["size"],
                    color=settings["color"]
                ),

                text=[
                    (
                        f"Sensor {sensor.node_id}"
                        f"<br>Type: {sensor.sensor_type}"
                        f"<br>State: {sensor.state}"
                        f"<br>Energy: "
                        f"{sensor.remaining_energy:.4f} J"
                        f"<br>Neighbors: "
                        f"{len(sensor.neighbors)}"
                    )
                    for sensor in group
                ],

                hovertemplate=(
                    "%{text}"
                    "<extra></extra>"
                ),

                name=state
            )
        )

    # --------------------------------
    # Sink
    # --------------------------------

    fig.add_trace(
        go.Scatter(
            x=[sink.x],
            y=[sink.y],

            mode="markers+text",

            marker=dict(
                symbol="star",
                size=20,
                color="#1f77b4"
            ),

            text=["SINK"],

            textposition="top center",

            name="Sink"
        )
    )

    # --------------------------------
    # Highlight route
    # --------------------------------

    if route is not None:

        route_x = []
        route_y = []

        for node_id in route.path:

            if node_id == sink.node_id:

                route_x.append(
                    sink.x
                )

                route_y.append(
                    sink.y
                )

            else:

                sensor = (
                    sensor_map[node_id]
                )

                route_x.append(
                    sensor.x
                )

                route_y.append(
                    sensor.y
                )

        fig.add_trace(
            go.Scatter(
                x=route_x,
                y=route_y,

                mode="lines+markers+text",

                line=dict(
                    width=4,
                    color="#8c00ff"
                ),

                marker=dict(
                    size=10
                ),

                text=[
                    str(node)
                    for node in route.path
                ],

                textposition="top center",

                name="Selected Route"
            )
        )

    fig.update_layout(
        title="Wireless Sensor Network",

        xaxis=dict(
            title="X (m)",
            range=[0, 2000]
        ),

        yaxis=dict(
            title="Y (m)",
            range=[0, 2000],
            scaleanchor="x",
            scaleratio=1
        ),

        height=720,

        hovermode="closest",

        legend=dict(
            orientation="h"
        ),

        margin=dict(
            l=20,
            r=20,
            t=60,
            b=20
        )
    )

    return fig