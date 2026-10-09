from pathlib import Path

import matplotlib.pyplot as plt


def plot_hop_distribution(
    routes: dict,
    show: bool = True,
    save: bool = True
):

    hop_counts = [
        route.hop_count
        for route in routes.values()
        if route is not None
    ]

    if not hop_counts:
        return

    fig, ax = plt.subplots(
        figsize=(9, 6)
    )

    minimum = min(hop_counts)
    maximum = max(hop_counts)

    bins = range(
        minimum,
        maximum + 2
    )

    ax.hist(
        hop_counts,
        bins=bins,
        align="left",
        edgecolor="black"
    )

    ax.set_xlabel(
        "Minimum Hop Count"
    )

    ax.set_ylabel(
        "Number of Sensors"
    )

    ax.set_title(
        "Minimum-Hop Distribution"
    )

    ax.grid(
        True,
        alpha=0.2
    )

    plt.tight_layout()

    if save:

        output_dir = Path(
            "outputs"
        )

        output_dir.mkdir(
            exist_ok=True
        )

        output_path = (
            output_dir
            / "minimum_hop_distribution.png"
        )

        plt.savefig(
            output_path,
            dpi=200
        )

        print(
            "Hop distribution saved to: "
            f"{output_path}"
        )

    if show:
        plt.show()

    else:
        plt.close(fig)


COLOR_MIN_HOP = "#F97316"    # Orange
COLOR_LB_ECMHR = "#0284C7"   # Blue


def _base_figure_layout(
    title: str,
    yaxis_title: str,
    higher_is_better: bool = True
):
    import plotly.graph_objects as go

    direction_hint = (
        "Cao hơn là tốt hơn ↑"
        if higher_is_better
        else "Thấp hơn là tốt hơn ↓"
    )

    hint_color = (
        "#16a34a"
        if higher_is_better
        else "#2563eb"
    )

    return go.Layout(
        title=dict(
            text=(
                f"<b>{title}</b> "
                f"<span style='font-size:12px; font-weight:normal; color:{hint_color}'>"
                f"({direction_hint})</span>"
            ),
            x=0.02,
            y=0.96
        ),
        xaxis=dict(
            title="Round",
            gridcolor="rgba(148, 163, 184, 0.2)",
            zeroline=False
        ),
        yaxis=dict(
            title=yaxis_title,
            gridcolor="rgba(148, 163, 184, 0.2)",
            zeroline=False
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(255, 255, 255, 0.7)"
        ),
        margin=dict(l=55, r=25, t=55, b=45),
        hovermode="x unified",
        template="plotly_white",
        height=360
    )


def create_comparison_figures(
    history_data: dict
) -> dict:
    """
    Build 4 comparison charts between Minimum-Hop and LB-ECMHR:
    1. Tỷ lệ node còn đường đến Sink (% trên tổng số node ban đầu)
    2. Dữ liệu Sink nhận tích lũy (KB hoặc MB)
    3. Năng lượng tiêu hao trên mỗi KB nhận thành công (J/KB, tính tích lũy)
    4. Số node còn sống (Số node)
    """
    import plotly.graph_objects as go

    mh_info = history_data.get("minimum_hop", {})
    lb_info = history_data.get("lb_ecmhr", {})

    mh_hist = mh_info.get("history", [])
    lb_hist = lb_info.get("history", [])

    total_nodes_mh = mh_info.get("total_nodes", 500)
    total_nodes_lb = lb_info.get("total_nodes", 500)

    fnd_mh = mh_info.get("fnd_round")
    fnd_lb = lb_info.get("fnd_round")

    rounds_mh = [r["round"] for r in mh_hist]
    rounds_lb = [r["round"] for r in lb_hist]

    def _add_fnd_lines(fig):
        if fnd_mh is not None:
            fig.add_vline(
                x=fnd_mh,
                line_width=1.5,
                line_dash="dash",
                line_color=COLOR_MIN_HOP,
                annotation_text=f"FND MH: R{fnd_mh}",
                annotation_position="top left",
                annotation_font=dict(size=10, color=COLOR_MIN_HOP)
            )
        if fnd_lb is not None:
            fig.add_vline(
                x=fnd_lb,
                line_width=1.5,
                line_dash="dash",
                line_color=COLOR_LB_ECMHR,
                annotation_text=f"FND LB: R{fnd_lb}",
                annotation_position="top right",
                annotation_font=dict(size=10, color=COLOR_LB_ECMHR)
            )

    # ----------------------------------------------------
    # 1. Tỷ lệ node còn đường đến Sink (%)
    # ----------------------------------------------------
    conn_mh = [
        (r.get("connected_alive_nodes", r.get("alive_nodes", 0)) / total_nodes_mh) * 100
        for r in mh_hist
    ]
    conn_lb = [
        (r.get("connected_alive_nodes", r.get("alive_nodes", 0)) / total_nodes_lb) * 100
        for r in lb_hist
    ]

    fig_conn = go.Figure(layout=_base_figure_layout(
        title="1. Tỷ lệ node còn đường đến Sink",
        yaxis_title="% trên tổng số node",
        higher_is_better=True
    ))
    fig_conn.add_trace(go.Scatter(
        x=rounds_mh,
        y=conn_mh,
        mode="lines",
        name="Minimum-Hop",
        line=dict(color=COLOR_MIN_HOP, width=2.5),
        hovertemplate="%{y:.2f}%"
    ))
    fig_conn.add_trace(go.Scatter(
        x=rounds_lb,
        y=conn_lb,
        mode="lines",
        name="LB-ECMHR",
        line=dict(color=COLOR_LB_ECMHR, width=2.5),
        hovertemplate="%{y:.2f}%"
    ))
    _add_fnd_lines(fig_conn)

    # ----------------------------------------------------
    # 2. Dữ liệu Sink nhận tích lũy (KB hoặc MB)
    # ----------------------------------------------------
    max_bytes = max(
        (mh_hist[-1].get("delivered_bytes", 0) if mh_hist else 0),
        (lb_hist[-1].get("delivered_bytes", 0) if lb_hist else 0)
    )

    if max_bytes >= 1024 * 1024:
        divisor = 1024 * 1024
        data_unit = "MB"
    else:
        divisor = 1024
        data_unit = "KB"

    data_mh = [r.get("delivered_bytes", 0) / divisor for r in mh_hist]
    data_lb = [r.get("delivered_bytes", 0) / divisor for r in lb_hist]

    fig_data = go.Figure(layout=_base_figure_layout(
        title="2. Dữ liệu Sink nhận tích lũy",
        yaxis_title=f"Dữ liệu tích lũy ({data_unit})",
        higher_is_better=True
    ))
    fig_data.add_trace(go.Scatter(
        x=rounds_mh,
        y=data_mh,
        mode="lines",
        name="Minimum-Hop",
        line=dict(color=COLOR_MIN_HOP, width=2.5),
        hovertemplate=f"%{{y:.2f}} {data_unit}"
    ))
    fig_data.add_trace(go.Scatter(
        x=rounds_lb,
        y=data_lb,
        mode="lines",
        name="LB-ECMHR",
        line=dict(color=COLOR_LB_ECMHR, width=2.5),
        hovertemplate=f"%{{y:.2f}} {data_unit}"
    ))
    _add_fnd_lines(fig_data)

    # ----------------------------------------------------
    # 3. Năng lượng tiêu hao trên mỗi KB nhận thành công (J/KB)
    # ----------------------------------------------------
    def _calc_j_per_kb(hist):
        values = []
        for r in hist:
            del_kb = r.get("delivered_bytes", 0) / 1024.0
            energy = r.get("total_energy_consumed_j", 0.0)
            if del_kb > 0:
                values.append(energy / del_kb)
            else:
                values.append(0.0)
        return values

    j_kb_mh = _calc_j_per_kb(mh_hist)
    j_kb_lb = _calc_j_per_kb(lb_hist)

    fig_efficiency = go.Figure(layout=_base_figure_layout(
        title="3. Năng lượng tiêu hao / KB nhận thành công",
        yaxis_title="J / KB (tính tích lũy)",
        higher_is_better=False
    ))
    fig_efficiency.add_trace(go.Scatter(
        x=rounds_mh,
        y=j_kb_mh,
        mode="lines",
        name="Minimum-Hop",
        line=dict(color=COLOR_MIN_HOP, width=2.5),
        hovertemplate="%{y:.4f} J/KB"
    ))
    fig_efficiency.add_trace(go.Scatter(
        x=rounds_lb,
        y=j_kb_lb,
        mode="lines",
        name="LB-ECMHR",
        line=dict(color=COLOR_LB_ECMHR, width=2.5),
        hovertemplate="%{y:.4f} J/KB"
    ))
    _add_fnd_lines(fig_efficiency)

    # ----------------------------------------------------
    # 4. Số node còn sống
    # ----------------------------------------------------
    alive_mh = [r.get("alive_nodes", 0) for r in mh_hist]
    alive_lb = [r.get("alive_nodes", 0) for r in lb_hist]

    fig_alive = go.Figure(layout=_base_figure_layout(
        title="4. Số node còn sống",
        yaxis_title="Số node còn sống",
        higher_is_better=True
    ))
    fig_alive.add_trace(go.Scatter(
        x=rounds_mh,
        y=alive_mh,
        mode="lines",
        name="Minimum-Hop",
        line=dict(color=COLOR_MIN_HOP, width=2.5),
        hovertemplate="%{y} nodes"
    ))
    fig_alive.add_trace(go.Scatter(
        x=rounds_lb,
        y=alive_lb,
        mode="lines",
        name="LB-ECMHR",
        line=dict(color=COLOR_LB_ECMHR, width=2.5),
        hovertemplate="%{y} nodes"
    ))
    _add_fnd_lines(fig_alive)

    return {
        "connectivity": fig_conn,
        "delivered_data": fig_data,
        "energy_per_kb": fig_efficiency,
        "alive_nodes": fig_alive
    }