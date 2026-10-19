import plotly.graph_objects as go


def build_edge_geometry(
    network
):

    sensor_map = {
        sensor.node_id: sensor
        for sensor in network.sensors
    }

    sink = network.sink

    edge_x = []
    edge_y = []

    for node_a, node_b in (
        network.graph.edges()
    ):

        if node_a == sink.node_id:

            x1 = sink.x
            y1 = sink.y

        else:

            sensor = (
                sensor_map[
                    node_a
                ]
            )

            x1 = sensor.x
            y1 = sensor.y

        if node_b == sink.node_id:

            x2 = sink.x
            y2 = sink.y

        else:

            sensor = (
                sensor_map[
                    node_b
                ]
            )

            x2 = sensor.x
            y2 = sensor.y

        edge_x.extend([
            x1,
            x2,
            None
        ])

        edge_y.extend([
            y1,
            y2,
            None
        ])

    return (
        edge_x,
        edge_y
    )


def create_network_figure(
    network,
    route=None,
    show_edges=False,
    edge_geometry=None,
    overloaded_nodes=None,
    sink_waypoints=None,
    sink_movement_history=None
):
    """
    Create an interactive Plotly visualization
    for the WSN topology.
    """

    sensors = network.sensors
    sink = network.sink
    graph = network.graph

    overloaded_nodes = overloaded_nodes or set()

    sensor_map = {
        sensor.node_id: sensor
        for sensor in sensors
    }

    fig = go.Figure()

    # --------------------------------
    # Neighbor links
    # --------------------------------

    if show_edges:

        if edge_geometry is None:

            edge_x, edge_y = (
                build_edge_geometry(
                    network
                )
            )

        else:

            edge_x, edge_y = (
                edge_geometry
            )

        fig.add_trace(
            go.Scattergl(
                x=edge_x,
                y=edge_y,

                mode="lines",

                line=dict(
                    width=0.5,
                    color=(
                        "rgba(120,120,120,0.18)"
                    )
                ),

                hoverinfo="skip",

                name=(
                    "Communication links"
                )
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
        "OVERLOADED": {
            "color": "#9467bd",
            "size": 8
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

    sensor_display_states = {}
    for sensor in sensors:
        if not sensor.is_alive():
            sensor_display_states[sensor.node_id] = "DEAD"
        elif sensor.node_id in overloaded_nodes:
            sensor_display_states[sensor.node_id] = "OVERLOADED"
        elif not sensor.relay_enabled:
            sensor_display_states[sensor.node_id] = "LOW_ENERGY"
        else:
            sensor_display_states[sensor.node_id] = "ALIVE"

    for state, settings in (
        state_settings.items()
    ):

        group = [
            sensor
            for sensor in sensors
            if sensor_display_states[sensor.node_id] == state
        ]

        if not group:
            continue

        fig.add_trace(
            go.Scatter(
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
                        f"<br>State: {sensor_display_states[sensor.node_id]}"
                        f"<br>Energy: "
                        f"{sensor.remaining_energy:.4f} J"
                        f"<br>Neighbors: "
                        f"{len(sensor.neighbors)}"
                    )
                    for sensor in group
                ],

                customdata=[
                    sensor.node_id
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
    # Sink Waypoints & Mobility Trail
    # --------------------------------

    if sink_waypoints:
        wp_x = [wp.x for wp in sink_waypoints]
        wp_y = [wp.y for wp in sink_waypoints]
        wp_names = [getattr(wp, "name", f"W{i}") for i, wp in enumerate(sink_waypoints)]
        is_dense = len(sink_waypoints) > 9
        fig.add_trace(
            go.Scatter(
                x=wp_x,
                y=wp_y,
                mode="markers" if is_dense else "markers+text",
                marker=dict(
                    symbol="diamond-open",
                    size=7 if is_dense else 10,
                    color="#8B5CF6",
                    line=dict(width=1.2)
                ),
                text=wp_names,
                textposition="bottom center",
                name="Candidate Positions" if is_dense else "Waypoints",
                hovertemplate="Ứng viên %{text}<br>Tọa độ: (%{x:.1f}, %{y:.1f})<extra></extra>"
            )
        )

    # --------------------------------
    # Sink Movement History Trail & Step Badges
    # --------------------------------

    if sink_movement_history:
        moved_steps = []
        for d in sink_movement_history:
            if isinstance(d, dict):
                from_p = d.get("from_pos")
                to_p = d.get("to_pos")
                if from_p and to_p and (from_p != to_p or d.get("distance_m", 0) > 0):
                    moved_steps.append({
                        "round": d.get("round", 0),
                        "from_pos": from_p,
                        "to_pos": to_p,
                        "from_wp": d.get("from_waypoint", "CENTER"),
                        "to_wp": d.get("waypoint", d.get("to_waypoint", "")),
                        "distance_m": d.get("distance_m", 0.0),
                        "reason": d.get("reason", "")
                    })
            elif getattr(d, "moved", False):
                moved_steps.append({
                    "round": getattr(d, "current_round", 0),
                    "from_pos": getattr(d, "from_pos", (0, 0)),
                    "to_pos": getattr(d, "to_pos", (0, 0)),
                    "from_wp": getattr(d, "from_waypoint", "CENTER"),
                    "to_wp": getattr(d, "to_waypoint", ""),
                    "distance_m": getattr(d, "distance_m", 0.0),
                    "reason": getattr(d, "reason", "")
                })

        if moved_steps:
            start_pos = moved_steps[0]["from_pos"]

            # 1. Điểm xuất phát ban đầu (W0 Center)
            fig.add_trace(
                go.Scatter(
                    x=[start_pos[0]],
                    y=[start_pos[1]],
                    mode="markers+text",
                    marker=dict(
                        symbol="circle",
                        size=14,
                        color="#10B981",
                        line=dict(width=2, color="#064E3B")
                    ),
                    text=["🏁 Xuất phát (W0)"],
                    textposition="top left",
                    textfont=dict(size=11, color="#047857"),
                    name="Xuất phát (W0)",
                    hovertemplate="<b>Vị trí xuất phát ban đầu (W0)</b><br>Tọa độ: (%{x:.1f}, %{y:.1f})<extra></extra>"
                )
            )

            # 2. Đường vẽ quỹ đạo di chuyển (Dashed Trajectory Line)
            trail_x = [start_pos[0]] + [s["to_pos"][0] for s in moved_steps]
            trail_y = [start_pos[1]] + [s["to_pos"][1] for s in moved_steps]
            fig.add_trace(
                go.Scatter(
                    x=trail_x,
                    y=trail_y,
                    mode="lines",
                    line=dict(
                        color="#06B6D4",
                        width=3,
                        dash="dash"
                    ),
                    name="Quỹ đạo di chuyển",
                    hoverinfo="skip"
                )
            )

            # 3. Các điểm trạm từng đi qua đánh số thứ tự bước di chuyển
            step_x = [s["to_pos"][0] for s in moved_steps]
            step_y = [s["to_pos"][1] for s in moved_steps]
            step_labels = [f"#{i+1}" for i in range(len(moved_steps))]
            step_hovers = [
                (
                    f"<b>Bước #{i+1} (Round {s['round']})</b><br>"
                    f"Đến: Waypoint {s['to_wp']}<br>"
                    f"Khoảng cách: {s['distance_m']:.1f} m<br>"
                    f"Lý do: {s['reason']}"
                )
                for i, s in enumerate(moved_steps)
            ]
            fig.add_trace(
                go.Scatter(
                    x=step_x,
                    y=step_y,
                    mode="markers+text",
                    marker=dict(
                        symbol="circle",
                        size=12,
                        color="#F59E0B",
                        line=dict(width=2, color="#78350F")
                    ),
                    text=step_labels,
                    textposition="top right",
                    textfont=dict(size=11, color="#B45309"),
                    name="Các bước di chuyển (#)",
                    customdata=step_hovers,
                    hovertemplate="%{customdata}<extra></extra>"
                )
            )

    # --------------------------------
    # Sink
    # --------------------------------

    sink_wp_label = getattr(sink, "current_waypoint", "CENTER")
    moves_cnt = getattr(sink, "movement_count", 0)

    fig.add_trace(
        go.Scatter(
            x=[sink.x],
            y=[sink.y],

            mode="markers+text",

            marker=dict(
                symbol="star",
                size=22,
                color="#0284C7",
                line=dict(width=2, color="#0C4A6E")
            ),

            text=[f"SINK ({sink_wp_label})"],

            customdata=["SINK"],

            textposition="top center",

            hovertemplate=(
                f"<b>Mobile Sink Node</b><br>"
                f"Waypoint: {sink_wp_label}<br>"
                f"Position: (%{{x:.1f}}, %{{y:.1f}})<br>"
                f"Movements: {moves_cnt}<extra></extra>"
            ),

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

                customdata=route.path,

                textposition="top center",

                name="Selected Route"
            )
        )

    fig.update_layout(
        title="Wireless Sensor Network",

        clickmode="event+select",

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