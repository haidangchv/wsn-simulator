from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import yaml

from core.network import WirelessSensorNetwork
from simulation.simulator import WSNSimulator
from topology.deployment import (
    create_sink,
    deploy_sensors
)

from streamlit_components.network_chart import (
    build_edge_geometry,
    create_network_figure
)
from experiments.compare_routing import (
    compare_algorithms
)
from visualization.routing import (
    create_comparison_figures
)

from environment.analyzer import (
    EnvironmentalAnalyzer
)

from environment.alerts import (
    build_zone_alerts
)

from environment.degradation import (
    calculate_zone_degradation
)

from visualization.environment import (
    create_confidence_map,
    create_degradation_map,
    create_elqi_zone_map,
    create_indicator_heatmap
)

from simulation.simulation_clock import (
    duration_to_rounds,
    round_to_days
)
from environment.temporal_analysis import (
    daily_statistics,
    hourly_statistics,
    monthly_statistics,
    weekly_statistics
)
from simulation.checkpoint import (
    CheckpointError,
    create_checkpoint_bytes,
    restore_checkpoint_bytes,
)




# -----------------------------------------
# PAGE CONFIG
# -----------------------------------------

st.set_page_config(
    page_title="WSN Simulator",
    page_icon="📡",
    layout="wide"
)


# -----------------------------------------
# CONFIG
# -----------------------------------------

@st.cache_data
def load_base_config():

    config_path = (
        Path(__file__).parent
        / "config.yaml"
    )

    with open(
        config_path,
        "r",
        encoding="utf-8"
    ) as file:

        return yaml.safe_load(file)


def create_simulation(config):

    sensors = deploy_sensors(
        config
    )

    sink = create_sink(
        config
    )

    network = WirelessSensorNetwork(
        sensors=sensors,
        sink=sink
    )

    network.build_topology()

    simulator = WSNSimulator(
        network=network,
        config=config
    )

    return network, simulator


def initialize_session():

    base_config = load_base_config()

    if "config" not in st.session_state:

        st.session_state.config = (
            deepcopy(base_config)
        )

    if (
        "network" not in st.session_state
        or "simulator" not in st.session_state
        or not hasattr(st.session_state.simulator, "find_current_route")
        or not hasattr(st.session_state.simulator, "set_routing_algorithm")
        or type(st.session_state.simulator) is not WSNSimulator
    ):

        network, simulator = (
            create_simulation(
                st.session_state.config
            )
        )

        st.session_state.network = (
            network
        )

        st.session_state.simulator = (
            simulator
        )

        st.session_state.edge_geometry = (
            build_edge_geometry(
                network
            )
        )

    if (
        "edge_geometry" not in st.session_state
        or st.session_state.edge_geometry is None
    ):

        st.session_state.edge_geometry = (
            build_edge_geometry(
                st.session_state.network
            )
        )

    if "selected_route" not in (
        st.session_state
    ):

        st.session_state.selected_route = (
            None
        )

    if "find_route_searched" not in (
        st.session_state
    ):

        st.session_state.find_route_searched = (
            False
        )

    if "source_sensor_select" not in (
        st.session_state
    ):

        st.session_state.source_sensor_select = (
            1
        )

    if "last_processed_map_click" not in (
        st.session_state
    ):

        st.session_state.last_processed_map_click = (
            None
        )


initialize_session()


# -----------------------------------------
# HEADER
# -----------------------------------------

st.title(
    "📡 Wireless Sensor Network Simulator"
)

st.caption(
    "500-node WSN | Minimum-Hop Routing | "
    "Energy Model | Packet Simulation"
)

if "restored_checkpoint_metadata" in st.session_state:
    _meta = st.session_state.restored_checkpoint_metadata
    _sim = st.session_state.simulator
    _alive_count = len([s for s in st.session_state.network.sensors if s.is_alive()])
    _rpd = getattr(_sim, "rounds_per_day", 24)
    st.info(
        f"♻️ **Mô Phỏng Đã Khôi Phục Từ Checkpoint** | "
        f"Round: **{_meta.get('round', 0):,}** ({round_to_days(_meta.get('round', 0), _rpd):.1f} days) | "
        f"Thời điểm lưu: **{_meta.get('created_at', 'N/A')}** | "
        f"Thuật toán: **{getattr(_sim, 'routing_algorithm', 'N/A').upper()}** | "
        f"Node sống: **{_alive_count}/{len(st.session_state.network.sensors)}**"
    )


# =========================================
# SIDEBAR
# =========================================

st.sidebar.header(
    "⚙️ Network Configuration"
)

current_config = (
    st.session_state.config
)

st.sidebar.metric(
    "Sensors",
    current_config["network"][
        "num_sensors"
    ]
)

st.sidebar.caption(
    "Simulation area: 2000 × 2000 m"
)


transmission_range = (
    st.sidebar.slider(
        "Transmission Range (m)",
        min_value=50,
        max_value=400,
        value=int(
            current_config[
                "sensor"
            ][
                "transmission_range_m"
            ]
        ),
        step=10
    )
)


initial_energy = (
    st.sidebar.number_input(
        "Initial Energy (J)",
        min_value=0.1,
        max_value=100.0,
        value=float(
            current_config[
                "sensor"
            ][
                "initial_energy_j"
            ]
        ),
        step=1.0
    )
)


energy_threshold = (
    st.sidebar.slider(
        "Low Energy Threshold (%)",
        min_value=1,
        max_value=90,
        value=int(
            current_config[
                "sensor"
            ][
                "energy_threshold_ratio"
            ]
            * 100
        )
    )
)


random_seed = (
    st.sidebar.number_input(
        "Random Seed",
        min_value=0,
        max_value=100000,
        value=int(
            current_config[
                "network"
            ][
                "random_seed"
            ]
        ),
        step=1
    )
)


show_edges = (
    st.sidebar.checkbox(
        "Show Neighbor Links",
        value=False
    )
)

st.sidebar.divider()

st.sidebar.subheader(
    "⏱ Simulation Time"
)

sidebar_duration_unit = st.sidebar.selectbox(
    "Đơn vị mô phỏng",
    ["Rounds", "Days", "Weeks", "Months"],
    index=0
)

sidebar_duration_val = st.sidebar.number_input(
    "Thời lượng",
    min_value=1,
    max_value=10000 if sidebar_duration_unit == "Rounds" else 365,
    value=100 if sidebar_duration_unit == "Rounds" else 7,
    step=10 if sidebar_duration_unit == "Rounds" else 1
)

sidebar_rounds = duration_to_rounds(
    value=sidebar_duration_val,
    unit=sidebar_duration_unit,
    rounds_per_day=getattr(
        st.session_state.simulator,
        "rounds_per_day",
        24
    )
)

st.sidebar.caption(
    f"{sidebar_duration_val} {sidebar_duration_unit} = {sidebar_rounds:,} rounds (1 round = 1 giờ)"
)

st.sidebar.divider()

st.sidebar.subheader(
    "🧭 Routing Configuration"
)

routing_options = {
    "Minimum-Hop BFS":
        "minimum_hop",
    "LB-ECMHR (Load Balanced)":
        "lb_ecmhr"
}

configured_algorithm = current_config.get(
    "routing",
    {}
).get(
    "algorithm",
    "lb_ecmhr"
)

algo_label = next(
    (
        label
        for label, val in routing_options.items()
        if val == configured_algorithm
    ),
    "LB-ECMHR (Load Balanced)"
)

selected_label = st.sidebar.selectbox(
    "Routing Algorithm",
    options=list(
        routing_options.keys()
    ),
    index=list(
        routing_options.keys()
    ).index(
        algo_label
    )
)

selected_routing = routing_options[
    selected_label
]

load_window = 20
overload_factor = 2.0
recovery_factor = 1.2
max_extra_hops = 1

if selected_routing == "lb_ecmhr":

    st.sidebar.markdown(
        "### ⚖️ Load Balancing"
    )

    lb_defaults = current_config.get(
        "routing",
        {}
    ).get(
        "lb_ecmhr",
        {}
    )

    load_window = st.sidebar.slider(
        "Load Window (rounds)",
        min_value=5,
        max_value=100,
        value=int(
            lb_defaults.get(
                "load_window_rounds",
                20
            )
        ),
        step=5
    )

    overload_factor = st.sidebar.slider(
        "Overload Factor",
        min_value=1.2,
        max_value=4.0,
        value=float(
            lb_defaults.get(
                "overload_factor",
                2.0
            )
        ),
        step=0.1
    )

    recovery_factor = st.sidebar.slider(
        "Recovery Factor",
        min_value=0.5,
        max_value=1.9,
        value=float(
            lb_defaults.get(
                "recovery_factor",
                1.2
            )
        ),
        step=0.1
    )

    max_extra_hops = st.sidebar.slider(
        "Maximum Extra Hops",
        min_value=0,
        max_value=3,
        value=int(
            lb_defaults.get(
                "max_extra_hops",
                1
            )
        ),
        step=1
    )

    if recovery_factor >= overload_factor:
        st.sidebar.error(
            "Recovery Factor must be smaller than Overload Factor."
        )
        st.stop()


# -----------------------------------------
# ENVIRONMENTAL SCENARIO
# -----------------------------------------

st.sidebar.divider()

st.sidebar.subheader(
    "🌍 Environmental Scenario"
)

spatial_diversity = st.sidebar.slider(
    "Spatial Diversity",
    min_value=0.2,
    max_value=2.0,
    value=float(
        current_config.get(
            "environment",
            {}
        ).get(
            "spatial_strength",
            1.0
        )
    ),
    step=0.1,
    help="Độ phân hóa không gian toàn bản đồ (spatial_strength)"
)

pollution_intensity = st.sidebar.slider(
    "Pollution Intensity",
    min_value=0.2,
    max_value=2.5,
    value=float(
        current_config.get(
            "environment",
            {}
        ).get(
            "pollution_strength",
            1.0
        )
    ),
    step=0.1,
    help="Mức độ ô nhiễm công nghiệp / giao thông (pollution_strength)"
)


# -----------------------------------------
# SIMULATION PERFORMANCE MODE
# -----------------------------------------

st.sidebar.divider()
st.sidebar.subheader("⚡ Chế độ Mô phỏng")

sim_mode_choice = st.sidebar.radio(
    "Hiệu năng mô phỏng",
    options=["🚀 Fast (Khuyên dùng khi chạy dài)", "🔍 Detailed (Phân tích chi tiết)"],
    index=0 if current_config.get("routing", {}).get("lb_ecmhr", {}).get("route_update_interval_rounds", 6) >= 6 else 1,
    help="Fast Mode: route update mỗi 6h, phân tích môi trường mỗi 24h, UI cập nhật batch 24 rounds.\nDetailed Mode: route update mỗi 1h, phân tích môi trường mỗi 6h, UI cập nhật batch 6 rounds."
)

if sim_mode_choice.startswith("🚀 Fast"):
    mode_route_interval = 6
    mode_env_interval = 24
    mode_ui_batch = 24
else:
    mode_route_interval = 1
    mode_env_interval = 6
    mode_ui_batch = 6

# Dynamically synchronize settings
if "routing" not in st.session_state.config:
    st.session_state.config["routing"] = {}
if "lb_ecmhr" not in st.session_state.config["routing"]:
    st.session_state.config["routing"]["lb_ecmhr"] = {}
st.session_state.config["routing"]["lb_ecmhr"]["route_update_interval_rounds"] = mode_route_interval
if "environment" in st.session_state.config:
    st.session_state.config["environment"]["analysis_interval_rounds"] = mode_env_interval

if hasattr(st.session_state.simulator, "route_manager"):
    st.session_state.simulator.route_manager.route_update_interval_rounds = mode_route_interval
st.session_state.simulator.environment_analysis_interval = mode_env_interval


# -----------------------------------------
# APPLY CONFIGURATION
# -----------------------------------------

if st.sidebar.button(
    "🔄 Generate Network",
    use_container_width=True
):

    new_config = deepcopy(
        load_base_config()
    )

    new_config[
        "network"
    ][
        "random_seed"
    ] = int(
        random_seed
    )

    new_config[
        "sensor"
    ][
        "transmission_range_m"
    ] = float(
        transmission_range
    )

    new_config[
        "sensor"
    ][
        "initial_energy_j"
    ] = float(
        initial_energy
    )

    new_config[
        "sensor"
    ][
        "energy_threshold_ratio"
    ] = (
        energy_threshold / 100
    )

    new_config[
        "routing"
    ][
        "algorithm"
    ] = selected_routing

    if selected_routing == "lb_ecmhr":
        if "lb_ecmhr" not in new_config["routing"]:
            new_config["routing"]["lb_ecmhr"] = {}
        lb_config = new_config["routing"]["lb_ecmhr"]
        lb_config["load_window_rounds"] = int(load_window)
        lb_config["overload_factor"] = float(overload_factor)
        lb_config["recovery_factor"] = float(recovery_factor)
        lb_config["max_extra_hops"] = int(max_extra_hops)
        lb_config["route_update_interval_rounds"] = mode_route_interval

    if "environment" not in new_config:
        new_config["environment"] = {}
    new_config["environment"]["spatial_strength"] = float(spatial_diversity)
    new_config["environment"]["pollution_strength"] = float(pollution_intensity)
    new_config["environment"]["analysis_interval_rounds"] = mode_env_interval

    network, simulator = (
        create_simulation(
            new_config
        )
    )

    st.session_state.config = (
        new_config
    )

    st.session_state.network = (
        network
    )

    st.session_state.simulator = (
        simulator
    )

    st.session_state.edge_geometry = (
        build_edge_geometry(
            network
        )
    )

    st.session_state.selected_route = (
        None
    )
    st.session_state.find_route_searched = (
        False
    )
    st.session_state.last_processed_map_click = (
        None
    )
    st.session_state.source_sensor_select = (
        1
    )

    st.session_state.pop("restored_checkpoint_metadata", None)

    st.rerun()


# -----------------------------------------
# RESET
# -----------------------------------------

if st.sidebar.button(
    "↩️ Reset Simulation",
    use_container_width=True
):

    network, simulator = (
        create_simulation(
            st.session_state.config
        )
    )

    st.session_state.network = (
        network
    )

    st.session_state.simulator = (
        simulator
    )

    st.session_state.edge_geometry = (
        build_edge_geometry(
            network
        )
    )

    st.session_state.selected_route = (
        None
    )
    st.session_state.find_route_searched = (
        False
    )
    st.session_state.last_processed_map_click = (
        None
    )
    st.session_state.source_sensor_select = (
        1
    )

    st.session_state.pop("restored_checkpoint_metadata", None)

    st.rerun()


# -----------------------------------------
# CHECKPOINT (SAVE / RESTORE)
# -----------------------------------------

st.sidebar.divider()
st.sidebar.subheader("💾 Checkpoint (Save / Restore)")

cur_sim = st.session_state.simulator
cur_rpd = getattr(cur_sim, "rounds_per_day", 24)
st.sidebar.caption(
    f"Round hiện tại: **{cur_sim.current_round:,}** "
    f"({round_to_days(cur_sim.current_round, cur_rpd):.1f} ngày)"
)

# Download Checkpoint
checkpoint_bytes = create_checkpoint_bytes(
    simulator=st.session_state.simulator,
    config=st.session_state.config,
    app_version="1.0"
)

checkpoint_filename = (
    f"wsn_checkpoint_round_{cur_sim.current_round}.wsnchk.gz"
)

st.sidebar.download_button(
    label="💾 Save Simulation",
    data=checkpoint_bytes,
    file_name=checkpoint_filename,
    mime="application/gzip",
    use_container_width=True,
    help="Tải file checkpoint nén (.wsnchk.gz) chứa toàn bộ simulator (topology, năng lượng, tải relay, môi trường, RNG, lịch sử)."
)

# Restore Checkpoint
uploaded_checkpoint = st.sidebar.file_uploader(
    "Khôi phục Simulation",
    type=["gz", "wsnchk"],
    key="checkpoint_uploader",
    help="Chọn file checkpoint (.wsnchk.gz) để tiếp tục chính xác từ trạng thái đã lưu."
)

if uploaded_checkpoint is not None:
    if st.sidebar.button(
        "♻️ Restore Checkpoint",
        type="primary",
        use_container_width=True
    ):
        try:
            checkpoint = restore_checkpoint_bytes(
                uploaded_checkpoint.getvalue()
            )
            restored_sim = checkpoint["simulator"]
            restored_cfg = checkpoint["config"]

            st.session_state.simulator = restored_sim
            st.session_state.config = restored_cfg
            st.session_state.network = restored_sim.network
            st.session_state.edge_geometry = build_edge_geometry(
                restored_sim.network
            )

            st.session_state.selected_route = None
            st.session_state.find_route_searched = False
            st.session_state.last_processed_map_click = None
            st.session_state.source_sensor_select = 1

            st.session_state.restored_checkpoint_metadata = {
                "created_at": checkpoint.get("created_at", "N/A"),
                "round": checkpoint.get("round", restored_sim.current_round),
                "app_version": checkpoint.get("app_version", "1.0"),
            }

            st.sidebar.success(
                f"Khôi phục thành công round {restored_sim.current_round}!"
            )
            st.rerun()

        except CheckpointError as exc:
            st.sidebar.error(str(exc))
        except Exception:
            st.sidebar.error("Checkpoint không tương thích với phiên bản hiện tại.")

# Auto Checkpoint Settings
with st.sidebar.expander("⚙️ Auto Checkpoint", expanded=False):
    auto_save_val = st.checkbox(
        "Bật Auto Checkpoint",
        value=bool(
            st.session_state.config.get("checkpoint", {}).get("auto_save", False)
        ),
        help="Tự động lưu checkpoint định kỳ vào thư mục checkpoints/"
    )
    auto_save_interval = st.number_input(
        "Chu kỳ lưu (rounds)",
        min_value=50,
        max_value=5000,
        value=int(
            st.session_state.config.get("checkpoint", {}).get("interval_rounds", 500)
        ),
        step=50
    )
    auto_save_keep = st.number_input(
        "Giữ lại checkpoint gần nhất",
        min_value=1,
        max_value=20,
        value=int(
            st.session_state.config.get("checkpoint", {}).get("keep_last", 3)
        ),
        step=1
    )

    if "checkpoint" not in st.session_state.config:
        st.session_state.config["checkpoint"] = {}
    st.session_state.config["checkpoint"]["auto_save"] = auto_save_val
    st.session_state.config["checkpoint"]["interval_rounds"] = int(auto_save_interval)
    st.session_state.config["checkpoint"]["keep_last"] = int(auto_save_keep)
    if hasattr(st.session_state.simulator, "config"):
        st.session_state.simulator.config["checkpoint"] = st.session_state.config["checkpoint"]


network = (
    st.session_state.network
)

simulator = (
    st.session_state.simulator
)

if not hasattr(simulator, "find_current_route"):
    import types
    simulator.find_current_route = types.MethodType(
        WSNSimulator.find_current_route,
        simulator
    )

if not hasattr(simulator, "set_routing_algorithm"):
    import types
    simulator.set_routing_algorithm = types.MethodType(
        WSNSimulator.set_routing_algorithm,
        simulator
    )




# =========================================
# NETWORK STATISTICS
# =========================================

topology_stats = (
    network.get_statistics()
)

st.subheader(
    "🌐 Network Topology"
)

col1, col2, col3, col4 = (
    st.columns(4)
)

col1.metric(
    "Sensors",
    topology_stats[
        "num_sensors"
    ]
)

col2.metric(
    "Edges",
    topology_stats[
        "num_edges"
    ]
)

col3.metric(
    "Connected to Sink",
    topology_stats[
        "connected_to_sink"
    ]
)

col4.metric(
    "Average Degree",
    f"{topology_stats['average_sensor_degree']:.2f}"
)

connectivity_ratio = (
    topology_stats[
        "connectivity_ratio"
    ]
)

if connectivity_ratio < 1.0:

    st.warning(
        f"Only "
        f"{connectivity_ratio * 100:.2f}% "
        f"of sensors have a path to the Sink."
    )

else:

    st.success(
        "All sensors are connected "
        "to the Sink."
    )


# =========================================
# ROUTING
# =========================================

algorithm_name = (
    "LB-ECMHR"
    if getattr(
        simulator,
        "routing_algorithm",
        "minimum_hop"
    ) == "lb_ecmhr"
    else "Minimum-Hop BFS"
)

st.subheader(
    f"🧭 Routing — {algorithm_name}"
)

route_col1, route_col2 = (
    st.columns(
        [1, 3]
    )
)

with route_col1:

    sensor_ids = [
        sensor.node_id
        for sensor in network.sensors
    ]

    # Handle map point click selection
    map_event = st.session_state.get("network_map")
    if map_event and isinstance(map_event, dict):
        selection = map_event.get("selection", {})
        points = selection.get("points", [])
        if points:
            last_pt = points[-1]
            cdata = last_pt.get("customdata")
            if isinstance(cdata, (list, tuple)) and len(cdata) > 0:
                cdata = cdata[0]
            if cdata is not None and cdata != "SINK":
                try:
                    cand_id = int(cdata)
                    if cand_id in sensor_ids:
                        click_sig = (
                            cand_id,
                            last_pt.get("curve_number"),
                            last_pt.get("point_index"),
                            last_pt.get("x"),
                            last_pt.get("y")
                        )
                        if click_sig != st.session_state.get("last_processed_map_click"):
                            st.session_state.last_processed_map_click = click_sig
                            st.session_state.source_sensor_select = cand_id
                            st.session_state.find_route_searched = True
                            st.session_state.last_searched_source = cand_id
                            if hasattr(simulator, "find_current_route"):
                                st.session_state.selected_route = (
                                    simulator.find_current_route(cand_id)
                                )
                            else:
                                st.session_state.selected_route = (
                                    network.find_minimum_hop_route(cand_id)
                                )
                except (ValueError, TypeError):
                    pass

    if st.session_state.get("source_sensor_select") not in sensor_ids:
        st.session_state.source_sensor_select = (
            sensor_ids[0] if sensor_ids else 1
        )

    selected_source = st.selectbox(
        "Source Sensor",
        sensor_ids,
        key="source_sensor_select"
    )

    st.caption("💡 Click on any node on the map to auto-select and find route")

    if st.button(
        "Find Route",
        use_container_width=True
    ):

        st.session_state.find_route_searched = (
            True
        )
        st.session_state.last_searched_source = (
            selected_source
        )

        if hasattr(
            simulator,
            "find_current_route"
        ):

            st.session_state.selected_route = (
                simulator.find_current_route(
                    selected_source
                )
            )

        else:

            st.session_state.selected_route = (
                network.find_minimum_hop_route(
                    selected_source
                )
            )


route = (
    st.session_state.selected_route
)


with route_col2:

    if route is not None:

        if getattr(
            route,
            "used_overload_fallback",
            False
        ):
            st.warning(
                "⚠️ Using Overload Fallback Route: no balanced detour available."
            )

        path_elements = []
        low_energy_relays = []

        for idx, node in enumerate(route.path):

            if node == network.sink.node_id:
                path_elements.append("SINK 🎯")

            else:
                sensor = network.get_sensor(node)

                if sensor.state == "LOW_ENERGY":
                    path_elements.append(
                        f"S{node} 🟡 ({sensor.remaining_energy:.2f}J)"
                    )
                    if idx > 0:
                        low_energy_relays.append(node)

                elif sensor.state == "DEAD":
                    path_elements.append(f"S{node} 🔴")

                else:
                    path_elements.append(f"S{node}")

        st.success(
            " → ".join(path_elements)
        )

        if low_energy_relays:
            st.warning(
                f"⚠️ Route traverses {len(low_energy_relays)} LOW_ENERGY relay(s): "
                f"{', '.join(f'Sensor {n}' for n in low_energy_relays)}. "
                "Switch to LB-ECMHR to reroute and protect low-battery nodes!"
            )

        r1, r2, r3 = st.columns(3)

        r1.metric(
            "Hop Count",
            route.hop_count
        )

        baseline_hops = getattr(
            route,
            "baseline_hop_count",
            route.hop_count
        )
        detour_hops = getattr(
            route,
            "detour_hops",
            0
        )

        r2.metric(
            "Baseline Hops",
            f"{baseline_hops} (+{detour_hops})"
        )

        r3.metric(
            "Route Distance",
            f"{route.total_distance_m:.2f} m"
        )

        r4, r5, r6 = st.columns(3)

        max_load_val = getattr(
            route,
            "max_relay_load",
            None
        )

        if max_load_val is not None:
            r4.metric(
                "Max Relay Load",
                f"{max_load_val:.2f}"
            )
        else:
            r4.metric(
                "Max Relay Load",
                "N/A"
            )

        bottleneck_val = getattr(
            route,
            "bottleneck_energy_j",
            None
        )

        if bottleneck_val is not None:
            r5.metric(
                "Bottleneck Energy",
                f"{bottleneck_val:.4f} J"
            )
        else:
            r5.metric(
                "Bottleneck Energy",
                "N/A"
            )

        used_fallback = getattr(
            route,
            "used_overload_fallback",
            False
        )
        r6.metric(
            "Overload Fallback",
            "Yes" if used_fallback else "No"
        )

    elif st.session_state.get("find_route_searched", False):

        searched_source = st.session_state.get(
            "last_searched_source",
            selected_source
        )

        if getattr(simulator, "routing_algorithm", "minimum_hop") == "lb_ecmhr":
            st.error(
                f"❌ No valid LB-ECMHR route found for Sensor {searched_source} to Sink! "
                "All relay paths to the Sink are blocked by LOW_ENERGY (≤ 20%) or DEAD nodes."
            )
        else:
            st.error(
                f"❌ No route found from Sensor {searched_source} to Sink."
            )

    else:

        st.info(
            "Select a sensor and click "
            "'Find Route'."
        )


# =========================================
# NETWORK MAP
# =========================================

overloaded_nodes = set()
if (
    getattr(simulator, "routing_algorithm", None) == "lb_ecmhr"
    and hasattr(simulator, "route_manager")
    and hasattr(simulator.route_manager, "load_tracker")
):
    overloaded_nodes = (
        simulator.route_manager.load_tracker.overloaded_nodes
    )

network_figure = (
    create_network_figure(
        network=network,
        route=route,
        show_edges=show_edges,
        edge_geometry=st.session_state.get(
            "edge_geometry"
        ),
        overloaded_nodes=overloaded_nodes
    )
)

st.plotly_chart(
    network_figure,
    use_container_width=True,
    key="network_map",
    on_select="rerun",
    selection_mode="points"
)


# =========================================
# SIMULATION CONTROL
# =========================================

st.divider()

st.subheader(
    "▶️ Simulation Control"
)

def run_simulation_batch(sim, num_rounds: int, label: str = ""):
    if num_rounds <= 5:
        sim.run(rounds=num_rounds)
        return

    progress_bar = st.progress(0.0)
    status_text = st.empty()

    def update_progress(current, total):
        progress_bar.progress(min(current / total, 1.0))
        status_text.caption(
            f"⏳ {label or 'Đang mô phỏng'}: {current:,} / {total:,} rounds (Round hiện tại: {sim.current_round:,})"
        )

    sim.run(
        rounds=num_rounds,
        progress_callback=update_progress,
        batch_size=mode_ui_batch
    )
    progress_bar.empty()
    status_text.empty()


sim_col_rounds, sim_col_time = st.columns(2)

with sim_col_rounds:

    st.markdown("##### 🔢 Chạy theo số Round")

    r1, r10, r50, r100 = st.columns(4)

    with r1:
        if st.button("1 Round", use_container_width=True, key="btn_run_1r"):
            run_simulation_batch(simulator, 1, "1 Round")
            st.session_state.selected_route = None
            st.session_state.find_route_searched = False
            st.rerun()

    with r10:
        if st.button("10 Rounds", use_container_width=True, key="btn_run_10r"):
            run_simulation_batch(simulator, 10, "10 Rounds")
            st.session_state.selected_route = None
            st.session_state.find_route_searched = False
            st.rerun()

    with r50:
        if st.button("50 Rounds", use_container_width=True, key="btn_run_50r"):
            run_simulation_batch(simulator, 50, "50 Rounds")
            st.session_state.selected_route = None
            st.session_state.find_route_searched = False
            st.rerun()

    with r100:
        if st.button("100 Rounds", use_container_width=True, key="btn_run_100r"):
            run_simulation_batch(simulator, 100, "100 Rounds")
            st.session_state.selected_route = None
            st.session_state.find_route_searched = False
            st.rerun()

    r_input_col, r_btn_col = st.columns([1.5, 1.5])

    with r_input_col:
        custom_rounds = st.number_input(
            "Số rounds tùy chọn",
            min_value=1,
            max_value=10000,
            value=100,
            step=10,
            key="custom_rounds_number_input"
        )

    with r_btn_col:
        st.write("")
        st.write("")
        if st.button(
            f"▶ Chạy {custom_rounds} Rounds",
            use_container_width=True,
            key="btn_run_custom_rounds"
        ):
            run_simulation_batch(simulator, int(custom_rounds), f"{custom_rounds} Rounds")
            st.session_state.selected_route = None
            st.session_state.find_route_searched = False
            st.rerun()

with sim_col_time:

    st.markdown("##### ⏱️ Chạy theo Thời gian (1 round = 1 giờ)")

    t1, t7, t30 = st.columns(3)

    with t1:
        if st.button("📅 +1 Ngày (24r)", use_container_width=True, key="btn_run_1d"):
            run_simulation_batch(simulator, 24, "1 Ngày (24 rounds)")
            st.session_state.selected_route = None
            st.session_state.find_route_searched = False
            st.rerun()

    with t7:
        if st.button("📆 +7 Ngày (168r)", use_container_width=True, key="btn_run_7d"):
            run_simulation_batch(simulator, 168, "7 Ngày (168 rounds)")
            st.session_state.selected_route = None
            st.session_state.find_route_searched = False
            st.rerun()

    with t30:
        if st.button("🗓 +30 Ngày (720r)", use_container_width=True, key="btn_run_30d"):
            run_simulation_batch(simulator, 720, "30 Ngày (720 rounds)")
            st.session_state.selected_route = None
            st.session_state.find_route_searched = False
            st.rerun()

    t_val_col, t_unit_col, t_btn_col = st.columns([1, 1, 1.5])

    with t_val_col:
        cust_val = st.number_input(
            "Thời lượng",
            min_value=1,
            max_value=365,
            value=7,
            step=1,
            key="custom_time_val_input"
        )

    with t_unit_col:
        cust_unit = st.selectbox(
            "Đơn vị",
            ["Days", "Weeks", "Months"],
            index=0,
            key="custom_time_unit_select"
        )

    with t_btn_col:
        rounds_calculated = duration_to_rounds(
            value=cust_val,
            unit=cust_unit,
            rounds_per_day=simulator.rounds_per_day
        )
        st.write("")
        st.write("")
        if st.button(
            f"🚀 Chạy ({rounds_calculated:,}r)",
            use_container_width=True,
            key="btn_run_custom_time"
        ):
            run_simulation_batch(simulator, rounds_calculated, f"{rounds_calculated:,} Rounds")
            st.session_state.selected_route = None
            st.session_state.find_route_searched = False
            st.rerun()


# =========================================
# CURRENT METRICS & CLOCK
# =========================================

metrics = (
    simulator.get_metrics()
)

current_dt = (
    simulator.clock.datetime_for_round(
        max(simulator.current_round, 1)
    )
)
elapsed_days = (
    simulator.clock.elapsed_days(
        simulator.current_round
    )
)

st.subheader(
    "⏱ Simulation Clock"
)

tm1, tm2, tm3, tm4 = st.columns(4)
tm1.metric("Current Round", f"{metrics['round']:,}")
tm2.metric("Simulation Date", current_dt.strftime("%d/%m/%Y"))
tm3.metric("Simulation Time", current_dt.strftime("%H:%M"))
tm4.metric("Elapsed Time", f"{elapsed_days:.2f} days")

st.caption(
    f"Quy ước: 1 round = 1 giờ mô phỏng | 24 rounds/ngày | "
    f"Tổng thời gian: {metrics['elapsed_seconds'] / 3600:.1f} giờ mô phỏng"
)

st.subheader(
    "📊 Network Status"
)

m1, m2, m3, m4 = (
    st.columns(4)
)

m1.metric(
    "Alive Nodes",
    metrics["alive_nodes"]
)

m2.metric(
    "Low Energy",
    metrics["low_energy_nodes"]
)

m3.metric(
    "Dead Nodes",
    metrics["dead_nodes"]
)

m4.metric(
    "PDR",
    f"{metrics['pdr'] * 100:.2f}%"
)


m5, m6, m7, m8 = (
    st.columns(4)
)

m5.metric(
    "App Goodput",
    (
        f"{metrics['throughput_bps'] / 1000:.4f} kbps"
        if metrics['throughput_bps'] < 1000
        else f"{metrics['throughput_bps'] / 1000:.2f} kbps"
    ),
    help="Application Goodput = Delivered bits / Simulation time"
)

m6.metric(
    "PHY Data Rate",
    f"{metrics.get('link_data_rate_bps', 250000) / 1000:.0f} kbps",
    help="Radio PHY channel speed = 250 kbps"
)

m7.metric(
    "Avg E2E Delay",
    f"{metrics['average_delay_ms']:.2f} ms"
)

m8.metric(
    "Avg Hop Count",
    f"{metrics['average_hop_count']:.2f}"
)


m9, m10, m11 = (
    st.columns(3)
)

m9.metric(
    "Energy Consumed",
    (
        f"{metrics['total_energy_consumed_j']:.4f} J"
    )
)

m10.metric(
    "Energy Remaining",
    (
        f"{metrics['total_remaining_energy_j']:.4f} J"
    )
)

m11.metric(
    "Energy Efficiency",
    (
        f"{metrics['energy_efficiency_bits_per_j']:.0f} bit/J"
    )
)

if metrics["dead_nodes"] > 0:

    st.warning(
        f"{metrics['dead_nodes']} "
        f"sensor nodes have died."
    )

if (
    metrics["fnd_round"]
    is not None
):

    fnd_days = round_to_days(
        metrics["fnd_round"],
        simulator.rounds_per_day
    )

    st.info(
        f"🏁 First Node Death (FND) occurred at round "
        f"{metrics['fnd_round']} "
        f"({fnd_days:.1f} simulation days)."
    )

st.subheader(
    "🚀 Data Transfer Performance"
)

transfer_metrics = (
    simulator.get_metrics()
)

t1, t2, t3, t4 = (
    st.columns(4)
)

t1.metric(
    "PHY Data Rate",
    (
        f"{transfer_metrics['link_data_rate_bps'] / 1000:.0f} kbps"
    )
)

t2.metric(
    "Actual Throughput",
    (
        f"{transfer_metrics['throughput_bps'] / 1000:.2f} kbps"
    )
)

t3.metric(
    "Average TX Time",
    (
        f"{transfer_metrics['average_transmission_time_ms']:.2f} ms"
    )
)

t4.metric(
    "Average E2E Delay",
    (
        f"{transfer_metrics['average_delay_ms']:.2f} ms"
    )
)

d1, d2, d3 = (
    st.columns(3)
)

d1.metric(
    "Delivered to Sink",
    (
        f"{transfer_metrics['delivered_data_mb']:.2f} MB"
    )
)

d2.metric(
    "Total Network TX",
    (
        f"{transfer_metrics['network_load_mb']:.2f} MB"
    )
)

d3.metric(
    "Energy Efficiency",
    (
        f"{transfer_metrics['energy_efficiency_bits_per_j']:.0f} bit/J"
    )
)

st.subheader(
    "🔋 Data Delivered Until Battery Depletion"
)

def format_lifetime_data(
    round_value,
    byte_value
):

    if (
        round_value is None
        or
        byte_value is None
    ):

        return "-"

    mb = (
        byte_value
        /
        (
            1024 ** 2
        )
    )

    return (
        f"{mb:.2f} MB "
        f"@ Round {round_value}"
    )

l1, l2, l3 = (
    st.columns(3)
)

l1.metric(
    "Until FND",
    format_lifetime_data(
        transfer_metrics[
            "fnd_round"
        ],

        transfer_metrics[
            "delivered_bytes_at_fnd"
        ]
    )
)

l2.metric(
    "Until HND",
    format_lifetime_data(
        transfer_metrics[
            "hnd_round"
        ],

        transfer_metrics[
            "delivered_bytes_at_hnd"
        ]
    )
)

l3.metric(
    "Until LND",
    format_lifetime_data(
        transfer_metrics[
            "lnd_round"
        ],

        transfer_metrics[
            "delivered_bytes_at_lnd"
        ]
    )
)

st.subheader(
    "🔗 Network Connectivity Lifetime"
)

c1, c2, c3, c4 = (
    st.columns(4)
)

c1.metric(
    "Connected Alive",
    transfer_metrics[
        "connected_alive_nodes"
    ]
)

c2.metric(
    "Connectivity",
    (
        f"{transfer_metrics['routing_connectivity_ratio'] * 100:.1f}%"
    )
)

c3.metric(
    "90% Connectivity",
    (
        transfer_metrics[
            "connectivity_90_round"
        ]
        or "-"
    )
)

c4.metric(
    "50% Connectivity",
    (
        transfer_metrics[
            "connectivity_50_round"
        ]
        or "-"
    )
)

st.progress(
    transfer_metrics[
        "routing_connectivity_ratio"
    ],

    text=(
        "Alive sensors currently "
        "able to reach the Sink"
    )
)



# =========================================
# ROUTING ENGINE PERFORMANCE
# =========================================

st.subheader(
    "⚡ Routing Engine"
)

if hasattr(simulator, "route_manager"):

    route_metrics = (
        simulator.route_manager.get_metrics()
    )

else:

    route_metrics = {
        "route_table_builds": 0,
        "routing_requests": 0,
        "routing_reroutes": 0,
        "route_cache_hit_ratio": 0.0
    }

rm1, rm2, rm3, rm4 = (
    st.columns(4)
)

rm1.metric(
    "Route Table Builds",
    route_metrics[
        "route_table_builds"
    ]
)

rm2.metric(
    "Route Requests",
    route_metrics[
        "routing_requests"
    ]
)

rm3.metric(
    "On-Demand Reroutes",
    route_metrics[
        "routing_reroutes"
    ]
)

rm4.metric(
    "Cache Hit Ratio",
    (
        f"{route_metrics['route_cache_hit_ratio'] * 100:.2f}%"
    )
)

if getattr(simulator, "routing_algorithm", None) == "lb_ecmhr":

    st.subheader(
        "⚖️ Relay Load Balancing"
    )

    lb_metrics = (
        simulator.get_metrics()
    )

    l1, l2, l3, l4 = (
        st.columns(4)
    )

    l1.metric(
        "Active Relays",
        lb_metrics.get(
            "active_relay_count",
            0
        )
    )

    l2.metric(
        "Overloaded Relays",
        lb_metrics.get(
            "overloaded_relay_count",
            0
        )
    )

    l3.metric(
        "Relay Load CV",
        (
            f"{lb_metrics.get('relay_load_cv', 0.0):.3f}"
        )
    )

    l4.metric(
        "Max Relay Load",
        lb_metrics.get(
            "max_relay_load",
            0
        )
    )

    r1, r2, r3 = (
        st.columns(3)
    )

    r1.metric(
        "Detour Routes",
        lb_metrics.get(
            "detour_route_count",
            0
        )
    )

    r2.metric(
        "Overload Fallbacks",
        lb_metrics.get(
            "overload_fallback_route_count",
            0
        )
    )

    r3.metric(
        "Avg Route Load",
        (
            f"{lb_metrics.get('average_route_max_relay_load', 0.0):.2f}"
        )
    )


# =========================================
# PACKET STATISTICS
# =========================================

st.subheader(
    "📦 Packet Statistics"
)

p1, p2, p3, p4 = (
    st.columns(4)
)

p1.metric(
    "Generated",
    metrics[
        "generated_packets"
    ]
)

p2.metric(
    "Delivered",
    metrics[
        "delivered_packets"
    ]
)

p3.metric(
    "Dropped",
    metrics[
        "dropped_packets"
    ]
)

p4.metric(
    "Delivered Data",
    (
        f"{metrics['delivered_bytes'] / 1024:.2f} KB"
    )
)


# =========================================
# NETWORK LIFETIME
# =========================================

st.subheader(
    "🔋 Network Lifetime"
)

total_nodes = len(
    network.sensors
)

alive_ratio = (
    metrics["alive_nodes"]
    / total_nodes
)

st.progress(
    alive_ratio,
    text=(
        f"Network Survival: "
        f"{alive_ratio * 100:.1f}%"
    )
)

life1, life2, life3 = (
    st.columns(3)
)

life1.metric(
    "FND",
    metrics["fnd_round"]
    if metrics["fnd_round"] is not None
    else "-"
)

life2.metric(
    "HND",
    metrics["hnd_round"]
    if metrics["hnd_round"] is not None
    else "-"
)

life3.metric(
    "LND",
    metrics["lnd_round"]
    if metrics["lnd_round"] is not None
    else "-"
)


# =========================================
# HISTORY CHARTS
# =========================================

if simulator.history:

    st.divider()

    st.subheader(
        "📈 Simulation History"
    )

    history_df = pd.DataFrame(
        simulator.history
    )

    history_df = (
        history_df.set_index(
            "round"
        )
    )

    chart1, chart2 = (
        st.columns(2)
    )

    with chart1:

        st.markdown(
            "**Alive Nodes**"
        )

        st.line_chart(
            history_df[
                ["alive_nodes"]
            ]
        )


    with chart2:

        st.markdown(
            "**Remaining Energy**"
        )

        st.line_chart(
            history_df[
                ["total_remaining_energy_j"]
            ]
        )


    chart3, chart4 = (
        st.columns(2)
    )

    with chart3:

        st.markdown(
            "**Packet Delivery Ratio**"
        )

        pdr_chart = (
            history_df[
                ["pdr"]
            ].copy()
        )

        pdr_chart["pdr"] *= 100

        st.line_chart(
            pdr_chart
        )


    with chart4:

        st.markdown(
            "**Throughput**"
        )

        throughput_chart = (
            history_df[
                ["throughput_bps"]
            ].copy()
        )

        throughput_chart[
            "throughput_bps"
        ] /= 1000

        st.line_chart(
            throughput_chart
        )


    chart5, chart6 = (
        st.columns(2)
    )

    with chart5:

        connectivity_chart = (
            history_df[
                [
                    "routing_connectivity_ratio"
                ]
            ]
            .copy()
        )

        connectivity_chart[
            "routing_connectivity_ratio"
        ] *= 100

        st.markdown(
            "**Routing Connectivity (%)**"
        )

        st.line_chart(
            connectivity_chart
        )

    with chart6:

        delivered_chart = (
            history_df[
                [
                    "delivered_bytes"
                ]
            ]
            .copy()
        )

        delivered_chart[
            "delivered_bytes"
        ] /= (
            1024 ** 2
        )

        delivered_chart = (
            delivered_chart.rename(
                columns={
                    "delivered_bytes":
                        "Delivered MB"
                }
            )
        )

        st.markdown(
            "**Cumulative Data Delivered to Sink**"
        )

        st.line_chart(
            delivered_chart
        )

    chart7, chart8 = (
        st.columns(2)
    )

    with chart7:

        st.markdown(
            "**Relay Load Balance**"
        )

        load_cols = [
            c
            for c in [
                "relay_load_cv",
                "overloaded_relay_count"
            ]
            if c in history_df.columns
        ]

        if load_cols:
            st.line_chart(
                history_df[load_cols]
            )

    with chart8:

        st.markdown(
            "**Network Energy State**"
        )

        energy_state_cols = [
            c
            for c in [
                "alive_nodes",
                "low_energy_nodes",
                "dead_nodes",
                "connected_alive_nodes",
                "disconnected_alive_nodes"
            ]
            if c in history_df.columns
        ]

        if energy_state_cols:
            st.line_chart(
                history_df[energy_state_cols]
            )



# =========================================
# ROUTING COMPARISON
# =========================================

st.divider()

st.subheader(
    "⚖️ Routing Algorithm Comparison"
)

comparison_rounds = (
    st.number_input(
        "Comparison rounds",
        min_value=10,
        max_value=5000,
        value=500,
        step=50
    )
)

if st.button(
    "Compare Minimum-Hop vs LB-ECMHR",
    type="primary"
):

    with st.spinner(
        f"Running routing comparison ({comparison_rounds} rounds)..."
    ):

        comparison_df, history_data = (
            compare_algorithms(
                config=(
                    st.session_state.config
                ),
                rounds=int(
                    comparison_rounds
                ),
                return_history=True
            )
        )

        st.session_state["comparison_df"] = (
            comparison_df
        )
        st.session_state["comparison_history"] = (
            history_data
        )

if (
    "comparison_df" in st.session_state
    and "comparison_history" in st.session_state
):

    comparison_df = (
        st.session_state["comparison_df"]
    )
    history_data = (
        st.session_state["comparison_history"]
    )

    display_columns = [
        "algorithm",
        "alive_nodes",
        "dead_nodes",
        "pdr",
        "average_hop_count",
        "total_energy_consumed_j",
        "energy_efficiency_bits_per_j",
        "fnd_round",
        "relay_load_cv",
        "overloaded_relay_count"
    ]

    valid_cols = [
        col for col in display_columns
        if col in comparison_df.columns
    ]

    st.dataframe(
        comparison_df[
            valid_cols
        ],
        use_container_width=True,
        hide_index=True
    )

    # -------------------------------------
    # FND DISPLAY
    # -------------------------------------
    fnd_mh = (
        history_data.get("minimum_hop", {})
        .get("fnd_round")
    )
    fnd_lb = (
        history_data.get("lb_ecmhr", {})
        .get("fnd_round")
    )

    st.markdown("#### 🏁 Thời điểm First Node Dead (FND)")
    fnd_c1, fnd_c2, fnd_c3 = st.columns([1, 1, 1.2])

    with fnd_c1:
        st.metric(
            "🟠 FND - Minimum-Hop",
            f"Round {fnd_mh}" if fnd_mh is not None else "Chưa có (100% còn sống)",
            help="Vòng đầu tiên mà một node bất kỳ trong mạng cạn kiệt năng lượng (Minimum-Hop)"
        )

    with fnd_c2:
        st.metric(
            "🔵 FND - LB-ECMHR",
            f"Round {fnd_lb}" if fnd_lb is not None else "Chưa có (100% còn sống)",
            help="Vòng đầu tiên mà một node bất kỳ trong mạng cạn kiệt năng lượng (LB-ECMHR)"
        )

    with fnd_c3:
        if fnd_mh is not None and fnd_lb is not None:
            delta_fnd = fnd_lb - fnd_mh
            pct = (delta_fnd / fnd_mh * 100) if fnd_mh > 0 else 0
            st.metric(
                "⏳ Hiệu quả cải thiện FND",
                f"{delta_fnd:+d} rounds",
                delta=f"{pct:+.1f}% so với Min-Hop"
            )
        elif fnd_mh is not None and fnd_lb is None:
            st.metric(
                "⏳ Hiệu quả cải thiện FND",
                f"> +{int(comparison_rounds) - fnd_mh} rounds",
                delta="LB-ECMHR chưa có node chết!"
            )
        else:
            st.metric(
                "⏳ Hiệu quả cải thiện FND",
                "Chưa có node chết",
                delta="Cả 2 duy trì 100% pin sống"
            )

    # -------------------------------------
    # 4 CHARTS (2 ROWS × 2 COLUMNS)
    # -------------------------------------
    figures = create_comparison_figures(
        history_data=history_data
    )

    st.markdown("#### 📊 Biểu đồ so sánh hiệu năng theo vòng (2×2)")

    row1_col1, row1_col2 = st.columns(2)
    with row1_col1:
        st.plotly_chart(
            figures["connectivity"],
            use_container_width=True
        )
    with row1_col2:
        st.plotly_chart(
            figures["delivered_data"],
            use_container_width=True
        )

    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        st.plotly_chart(
            figures["energy_per_kb"],
            use_container_width=True
        )
    with row2_col2:
        st.plotly_chart(
            figures["alive_nodes"],
            use_container_width=True
        )

    st.caption(
        "💡 **Ghi chú đánh giá:** "
        "🟠 **Minimum-Hop** (màu cam) | 🔵 **LB-ECMHR** (màu xanh). "
        "Ở biểu đồ 1, 2 và 4: đường **cao hơn** là tốt hơn; "
        "ở biểu đồ 3: đường **thấp hơn** là tốt hơn (chi phí năng lượng J/KB thấp hơn)."
    )


# =========================================
# NODE TABLE
# =========================================

st.divider()

with st.expander(
    "🔍 Sensor Node Details"
):

    node_records = []

    for sensor in network.sensors:

        recent_fwd = 0
        load_fac = 0.0
        is_ovld = False

        if (
            getattr(simulator, "routing_algorithm", None) == "lb_ecmhr"
            and hasattr(simulator, "route_manager")
            and hasattr(simulator.route_manager, "load_tracker")
        ):
            recent_fwd = (
                simulator
                .route_manager
                .load_tracker
                .get_recent_forwarded(
                    sensor.node_id
                )
            )
            load_fac = round(
                simulator
                .route_manager
                .load_tracker
                .get_load_factor(
                    sensor.node_id
                ),
                2
            )
            is_ovld = (
                simulator
                .route_manager
                .load_tracker
                .is_overloaded(
                    sensor.node_id
                )
            )

        node_records.append({
            "ID":
                sensor.node_id,

            "Type":
                sensor.sensor_type,

            "X":
                round(
                    sensor.x,
                    2
                ),

            "Y":
                round(
                    sensor.y,
                    2
                ),

            "Energy (J)":
                round(
                    sensor.remaining_energy,
                    6
                ),

            "State":
                sensor.state,

            "Neighbors":
                len(
                    sensor.neighbors
                ),

            "Generated":
                sensor.generated_packets,

            "Forwarded":
                sensor.forwarded_packets,

            "Received":
                sensor.received_packets,

            "recent_forwarded":
                recent_fwd,

            "load_factor":
                load_fac,

            "overloaded":
                is_ovld
        })

    node_df = pd.DataFrame(
        node_records
    )

    st.dataframe(
        node_df,
        use_container_width=True,
        hide_index=True
    )


# =========================================
# ENVIRONMENTAL INTELLIGENCE
# =========================================

st.divider()

st.header(
    "🌿 Environmental Intelligence"
)

env_cfg = st.session_state.config.get("environment", {})
s_val = env_cfg.get("spatial_strength", 1.0)
p_val = env_cfg.get("pollution_strength", 1.0)
with st.expander("🌍 Kịch Bản Môi Trường Hiện Tại (Environmental Scenario)", expanded=False):
    c_sc1, c_sc2 = st.columns(2)
    c_sc1.metric("Spatial Diversity (Phân hóa không gian)", f"{s_val:.1f}")
    c_sc2.metric("Pollution Intensity (Cường độ ô nhiễm)", f"{p_val:.1f}")
    st.caption(
        "Mô hình không gian sử dụng các Gaussian latent fields: Khu công nghiệp (NE), "
        "Giao thông trục chính, Đảo nhiệt đô thị, Vùng sinh thái ẩm/xanh, Vùng ô nhiễm nước, "
        "kết hợp chu kỳ ngày-đêm (24h) và tương quan tự hồi quy thời gian AR(1) (ρ=0.72). "
        "Để đổi kịch bản, chỉnh ở thanh bên và bấm '🔄 Generate Network' để đảm bảo tính nhất quán chuỗi thời gian."
    )

collector = (
    simulator.environment_collector
)

if (
    collector is None
    or
    not collector.received_records
):

    st.info(
        "Run at least one simulation round "
        "to collect environmental data."
    )

else:

    analyzer = (
        EnvironmentalAnalyzer(
            st.session_state.config
        )
    )

    (
        hourly_tab,
        daily_tab,
        weekly_tab,
        monthly_tab,
        trend_tab,
        heatmap_tab,
        quality_tab,
        degradation_tab
    ) = st.tabs([
        "⏰ Hourly (24h)",
        "📅 Daily",
        "📆 Weekly",
        "🗓 Monthly",
        "📈 All Trends",
        "🌡 Heatmaps",
        "🗺 Living Quality",
        "📉 Degradation"
    ])

    environmental_df = (
        collector.received_dataframe()
    )

    with hourly_tab:

        st.subheader(
            "⏰ Chu kỳ 24 Giờ Gần Nhất (Day-Night Cycle)"
        )

        if not environmental_df.empty:

            max_round = int(
                environmental_df["round"].max()
            )

            start_24h_round = max(
                1,
                max_round - 23
            )

            recent_24h_df = environmental_df[
                environmental_df["round"] >= start_24h_round
            ].copy()

            if not recent_24h_df.empty:

                hourly_piv = (
                    recent_24h_df.groupby(
                        ["round", "sensor_type"]
                    )["value"]
                    .mean()
                    .unstack()
                )

                st.caption(
                    f"Hiển thị từ Round {start_24h_round} đến Round {max_round} "
                    f"({len(recent_24h_df):,} bản ghi nhận được tại Sink)"
                )

                st.line_chart(hourly_piv)

                st.markdown("##### Bảng thống kê theo giờ")

                st.dataframe(
                    hourly_statistics(recent_24h_df),
                    use_container_width=True,
                    hide_index=True
                )

        else:

            st.info("Chưa có dữ liệu đo môi trường.")

    with daily_tab:

        st.subheader(
            "📅 Thống Kê Theo Ngày (Daily Statistics)"
        )

        if not environmental_df.empty:

            daily_df = daily_statistics(
                environmental_df
            )

            if not daily_df.empty:

                sensor_types_daily = sorted(
                    daily_df["sensor_type"].unique()
                )

                sel_sensor_daily = st.selectbox(
                    "Chọn loại cảm biến (Daily)",
                    sensor_types_daily,
                    key="daily_sensor_select"
                )

                f_daily = daily_df[
                    daily_df["sensor_type"] == sel_sensor_daily
                ].copy()

                f_daily["Date"] = (
                    f_daily["timestamp"]
                    .dt.strftime("%d/%m/%Y")
                )

                chart_daily = (
                    f_daily.set_index("Date")[
                        ["mean", "min", "max"]
                    ]
                )

                st.line_chart(chart_daily)

                st.dataframe(
                    f_daily,
                    use_container_width=True,
                    hide_index=True
                )

            else:

                st.info("Chưa đủ dữ liệu ngày để tổng hợp.")

    with weekly_tab:

        st.subheader(
            "📆 Thống Kê Theo Tuần (Weekly Statistics - 168 Rounds/Tuần)"
        )

        if not environmental_df.empty:

            weekly_df = weekly_statistics(
                environmental_df
            )

            if not weekly_df.empty:

                sensor_types_weekly = sorted(
                    weekly_df["sensor_type"].unique()
                )

                sel_sensor_weekly = st.selectbox(
                    "Chọn loại cảm biến (Weekly)",
                    sensor_types_weekly,
                    key="weekly_sensor_select"
                )

                f_weekly = weekly_df[
                    weekly_df["sensor_type"] == sel_sensor_weekly
                ].copy()

                f_weekly["Week"] = (
                    f_weekly["timestamp"]
                    .dt.strftime("%Y-W%W")
                )

                chart_weekly = (
                    f_weekly.set_index("Week")[
                        ["mean", "min", "max"]
                    ]
                )

                st.line_chart(chart_weekly)

                st.dataframe(
                    f_weekly,
                    use_container_width=True,
                    hide_index=True
                )

            else:

                st.info("Cần ít nhất 1 tuần (168 rounds) để tổng hợp tuần đầy đủ.")

    with monthly_tab:

        st.subheader(
            "🗓 Thống Kê Theo Tháng Lịch Thực (Monthly Statistics)"
        )

        if not environmental_df.empty:

            monthly_df = monthly_statistics(
                environmental_df
            )

            if not monthly_df.empty:

                sensor_types_monthly = sorted(
                    monthly_df["sensor_type"].unique()
                )

                sel_sensor_monthly = st.selectbox(
                    "Chọn loại cảm biến (Monthly)",
                    sensor_types_monthly,
                    key="monthly_sensor_select"
                )

                f_monthly = monthly_df[
                    monthly_df["sensor_type"] == sel_sensor_monthly
                ].copy()

                chart_monthly = (
                    f_monthly.set_index("month")[
                        ["mean", "min", "max"]
                    ]
                )

                st.line_chart(chart_monthly)

                st.dataframe(
                    f_monthly,
                    use_container_width=True,
                    hide_index=True
                )

            else:

                st.info("Chưa có dữ liệu tháng.")

    with trend_tab:

        indicator = (
            st.selectbox(
                "Indicator",
                [
                    "temperature",
                    "humidity",
                    "pm25",
                    "wind",
                    "water_quality"
                ],
                key="trend_indicator"
            )
        )

        indicator_df = (
            environmental_df[
                environmental_df[
                    "sensor_type"
                ]
                ==
                indicator
            ]
            .copy()
        )

        if not indicator_df.empty:

            average_trend = (
                indicator_df
                .groupby(
                    "round"
                )[
                    "value"
                ]
                .mean()
                .to_frame(
                    "Average"
                )
            )

            st.subheader(
                "Average Trend"
            )

            st.line_chart(
                average_trend
            )

            sensor_ids = sorted(
                indicator_df[
                    "source_id"
                ]
                .unique()
            )

            selected_sensor = (
                st.selectbox(
                    "Sensor",
                    sensor_ids,
                    key="environment_sensor"
                )
            )

            sensor_history = (
                indicator_df[
                    indicator_df[
                        "source_id"
                    ]
                    ==
                    selected_sensor
                ]
                .set_index(
                    "round"
                )
            )

            st.subheader(
                f"Sensor {selected_sensor}"
            )

            st.line_chart(
                sensor_history[
                    ["value"]
                ]
            )

    with heatmap_tab:

        indicator = (
            st.selectbox(
                "Heatmap Indicator",
                [
                    "temperature",
                    "humidity",
                    "pm25",
                    "wind",
                    "water_quality"
                ],
                key="heatmap_indicator"
            )
        )

        snapshot = (
            analyzer.latest_sensor_snapshot(
                collector=collector,

                current_round=(
                    simulator.current_round
                ),

                sensor_type=indicator
            )
        )

        if snapshot.empty:

            st.warning(
                "No sufficiently recent data "
                "is available for this indicator."
            )

        else:

            latest1, latest2, latest3 = (
                st.columns(3)
            )

            latest1.metric(
                "Average",
                f"{snapshot['value'].mean():.2f}"
            )

            latest2.metric(
                "Minimum",
                f"{snapshot['value'].min():.2f}"
            )

            latest3.metric(
                "Maximum",
                f"{snapshot['value'].max():.2f}"
            )

            heatmap_figure = (
                create_indicator_heatmap(
                    snapshot=snapshot,

                    sensor_type=indicator,

                    config=(
                        st.session_state.config
                    ),

                    sink=network.sink
                )
            )

            st.plotly_chart(
                heatmap_figure,
                use_container_width=True
            )

            st.caption(
                f"Based on "
                f"{len(snapshot)} recent sensor "
                f"measurements received by the Sink."
            )

    with quality_tab:

        zone_df = (
            analyzer.build_zone_snapshot(
                collector=collector,

                current_round=(
                    simulator.current_round
                )
            )
        )

        valid_zones = (
            zone_df[
                zone_df[
                    "elqi"
                ]
                .notna()
            ]
            .copy()
        )

        if valid_zones.empty:

            st.warning(
                "Not enough environmental data "
                "to calculate ELQI."
            )

        else:

            confidence_weights = (
                valid_zones[
                    "confidence"
                ]
                .clip(
                    lower=0.01
                )
            )

            overall_elqi = (
                (
                    valid_zones[
                        "elqi"
                    ]
                    *
                    confidence_weights
                )
                .sum()
                /
                confidence_weights.sum()
            )

            best_zone = (
                valid_zones.loc[
                    valid_zones[
                        "elqi"
                    ].idxmax()
                ]
            )

            worst_zone = (
                valid_zones.loc[
                    valid_zones[
                        "elqi"
                    ].idxmin()
                ]
            )

            low_confidence_count = int(
                valid_zones[
                    "low_confidence"
                ]
                .sum()
            )

            q1, q2, q3, q4 = (
                st.columns(4)
            )

            q1.metric(
                "Overall ELQI",
                f"{overall_elqi:.1f}"
            )

            q2.metric(
                "Best Zone",
                (
                    f"{best_zone['zone_id']} "
                    f"({best_zone['elqi']:.1f})"
                )
            )

            q3.metric(
                "Worst Zone",
                (
                    f"{worst_zone['zone_id']} "
                    f"({worst_zone['elqi']:.1f})"
                )
            )

            q4.metric(
                "Low Confidence Zones",
                low_confidence_count
            )

            quality_figure = (
                create_elqi_zone_map(
                    zone_dataframe=(
                        zone_df
                    ),

                    config=(
                        st.session_state.config
                    ),

                    sink=(
                        network.sink
                    )
                )
            )

            st.plotly_chart(
                quality_figure,
                use_container_width=True
            )

            st.caption(
                "⚠ indicates a zone whose "
                "environmental estimate has "
                "low data confidence."
            )

            with st.expander(
                "📡 Data Confidence Map"
            ):

                confidence_figure = (
                    create_confidence_map(
                        zone_dataframe=(
                            zone_df
                        ),

                        config=(
                            st.session_state.config
                        )
                    )
                )

                st.plotly_chart(
                    confidence_figure,
                    use_container_width=True
                )

            st.subheader(
                "Zone Assessment"
            )

            display_columns = [
                "zone_id",
                "temperature",
                "humidity",
                "pm25",
                "wind",
                "water_quality",
                "temperature_score",
                "humidity_score",
                "pm25_score",
                "wind_score",
                "water_quality_score",
                "elqi",
                "rating",
                "confidence"
            ]

            zone_display = (
                zone_df[
                    display_columns
                ]
                .copy()
            )

            numeric_columns = [
                column
                for column
                in zone_display.columns
                if column
                not in [
                    "zone_id",
                    "rating"
                ]
            ]

            zone_display[
                numeric_columns
            ] = (
                zone_display[
                    numeric_columns
                ]
                .round(
                    2
                )
            )

            st.dataframe(
                zone_display,

                use_container_width=True,

                hide_index=True
            )

            rank1, rank2 = (
                st.columns(2)
            )

            with rank1:

                st.markdown(
                    "### 🏆 Best Environmental Areas"
                )

                best_areas = (
                    valid_zones
                    .sort_values(
                        "elqi",
                        ascending=False
                    )
                    .head(10)
                )

                st.dataframe(
                    best_areas[
                        [
                            "zone_id",
                            "elqi",
                            "rating",
                            "confidence"
                        ]
                    ],

                    hide_index=True,

                    use_container_width=True
                )

            with rank2:

                st.markdown(
                    "### ⚠ Areas Requiring Attention"
                )

                worst_areas = (
                    valid_zones
                    .sort_values(
                        "elqi",
                        ascending=True
                    )
                    .head(10)
                )

                st.dataframe(
                    worst_areas[
                        [
                            "zone_id",
                            "elqi",
                            "rating",
                            "confidence"
                        ]
                    ],

                    hide_index=True,

                    use_container_width=True
                )

            st.subheader(
                "🔍 Zone Detail"
            )

            selected_zone_id = (
                st.selectbox(
                    "Zone",
                    zone_df[
                        "zone_id"
                    ].tolist()
                )
            )

            selected_zone = (
                zone_df[
                    zone_df[
                        "zone_id"
                    ]
                    ==
                    selected_zone_id
                ]
                .iloc[0]
            )

            z1, z2, z3 = (
                st.columns(3)
            )

            z1.metric(
                "ELQI",
                (
                    f"{selected_zone['elqi']:.1f}"
                    if not np.isnan(
                        selected_zone[
                            "elqi"
                        ]
                    )
                    else "-"
                )
            )

            z2.metric(
                "Rating",
                selected_zone[
                    "rating"
                ]
            )

            z3.metric(
                "Confidence",
                (
                    f"{selected_zone['confidence'] * 100:.1f}%"
                )
            )

            zone_scores = pd.DataFrame({

                "Indicator": [
                    "Temperature",
                    "Humidity",
                    "PM2.5",
                    "Wind",
                    "Water Quality"
                ],

                "Value": [
                    selected_zone[
                        "temperature"
                    ],

                    selected_zone[
                        "humidity"
                    ],

                    selected_zone[
                        "pm25"
                    ],

                    selected_zone[
                        "wind"
                    ],

                    selected_zone[
                        "water_quality"
                    ]
                ],

                "Score": [
                    selected_zone[
                        "temperature_score"
                    ],

                    selected_zone[
                        "humidity_score"
                    ],

                    selected_zone[
                        "pm25_score"
                    ],

                    selected_zone[
                        "wind_score"
                    ],

                    selected_zone[
                        "water_quality_score"
                    ]
                ]
            })

            st.dataframe(
                zone_scores.round(2),

                use_container_width=True,

                hide_index=True
            )

    with degradation_tab:

        tracker = (
            simulator
            .zone_history_tracker
        )

        if (
            tracker is None
        ):

            st.info(
                "Environmental history "
                "is not available."
            )

        else:

            history_df = (
                tracker.dataframe()
            )

            if history_df.empty:

                st.info(
                    "Run the simulation to "
                    "collect ELQI history."
                )

            else:

                available_snapshot_rounds = (
                    sorted(
                        history_df[
                            "round"
                        ].unique()
                    )
                )

                st.caption(
                    f"Environmental snapshots: "
                    f"{len(available_snapshot_rounds)} | "
                    f"Latest snapshot: "
                    f"{max(available_snapshot_rounds)}"
                )

                degradation_df = (
                    calculate_zone_degradation(
                        history_dataframe=(
                            history_df
                        ),

                        config=(
                            st.session_state.config
                        ),

                        current_round=(
                            simulator.current_round
                        )
                    )
                )

                if degradation_df.empty:

                    st.info(
                        "More environmental history "
                        "is required."
                    )

                else:

                    full_lookback = bool(
                        degradation_df[
                            "full_lookback"
                        ]
                        .iloc[0]
                    )

                    if not full_lookback:

                        st.warning(
                            "The configured degradation "
                            "lookback window has not yet "
                            "been fully reached. Current "
                            "results use the earliest "
                            "available snapshot."
                        )

                    reliable = (
                        degradation_df[
                            degradation_df[
                                "degradation_status"
                            ]
                            !=
                            "Độ tin cậy thấp"
                        ]
                        .copy()
                    )

                    declining = (
                        reliable[
                            reliable[
                                "delta_elqi"
                            ]
                            <
                            -3
                        ]
                    )

                    severe = (
                        reliable[
                            reliable[
                                "degradation_status"
                            ]
                            ==
                            "Suy giảm nghiêm trọng"
                        ]
                    )

                    if not reliable.empty:

                        average_delta = (
                            reliable[
                                "delta_elqi"
                            ].mean()
                        )

                        worst_decline = (
                            reliable.loc[
                                reliable[
                                    "delta_elqi"
                                ].idxmin()
                            ]
                        )

                    else:

                        average_delta = 0.0
                        worst_decline = None

                    d1, d2, d3, d4 = (
                        st.columns(4)
                    )

                    d1.metric(
                        "Average Δ ELQI",
                        f"{average_delta:+.2f}"
                    )

                    d2.metric(
                        "Declining Zones",
                        len(
                            declining
                        )
                    )

                    d3.metric(
                        "Severe Decline",
                        len(
                            severe
                        )
                    )

                    d4.metric(
                        "Worst Decline",
                        (
                            f"{worst_decline['zone_id']} "
                            f"({worst_decline['delta_elqi']:+.1f})"
                            if worst_decline
                            is not None
                            else "-"
                        )
                    )

                    degradation_figure = (
                        create_degradation_map(
                            degradation_dataframe=(
                                degradation_df
                            ),

                            config=(
                                st.session_state.config
                            ),

                            sink=(
                                network.sink
                            )
                        )
                    )

                    st.plotly_chart(
                        degradation_figure,
                        use_container_width=True
                    )

                    st.subheader(
                        "⚠ Fastest Environmental Decline"
                    )

                    fastest_decline = (
                        reliable
                        .sort_values(
                            "delta_elqi",
                            ascending=True
                        )
                        .head(10)
                    )

                    st.dataframe(
                        fastest_decline[
                            [
                                "zone_id",
                                "baseline_elqi",
                                "current_elqi",
                                "delta_elqi",
                                "trend_per_100_rounds",
                                "degradation_status",
                                "comparison_confidence"
                            ]
                        ]
                        .round(2),

                        use_container_width=True,

                        hide_index=True
                    )

                    alerts_df = (
                        build_zone_alerts(
                            degradation_dataframe=(
                                degradation_df
                            ),

                            config=(
                                st.session_state.config
                            )
                        )
                    )

                    st.subheader(
                        "🚨 Environmental Alerts"
                    )

                    if alerts_df.empty:

                        st.success(
                            "No environmental warning "
                            "conditions detected."
                        )

                    else:

                        critical_count = (
                            alerts_df[
                                alerts_df[
                                    "severity"
                                ]
                                ==
                                "CRITICAL"
                            ]
                            .shape[0]
                        )

                        warning_count = (
                            alerts_df[
                                alerts_df[
                                    "severity"
                                ]
                                ==
                                "WARNING"
                            ]
                            .shape[0]
                        )

                        data_count = (
                            alerts_df[
                                alerts_df[
                                    "severity"
                                ]
                                ==
                                "DATA"
                            ]
                            .shape[0]
                        )

                        a1, a2, a3 = (
                            st.columns(3)
                        )

                        a1.metric(
                            "Critical",
                            critical_count
                        )

                        a2.metric(
                            "Warnings",
                            warning_count
                        )

                        a3.metric(
                            "Data Quality Alerts",
                            data_count
                        )

                        st.dataframe(
                            alerts_df.round(2),

                            use_container_width=True,

                            hide_index=True
                        )

                    st.subheader(
                        "📈 Zone ELQI History"
                    )

                    selected_history_zone = (
                        st.selectbox(
                            "Zone History",
                            sorted(
                                history_df[
                                    "zone_id"
                                ]
                                .unique()
                            ),
                            key=(
                                "degradation_zone"
                            )
                        )
                    )

                    zone_history = (
                        history_df[
                            history_df[
                                "zone_id"
                            ]
                            ==
                            selected_history_zone
                        ]
                        .sort_values(
                            "round"
                        )
                        .set_index(
                            "round"
                        )
                    )

                    st.line_chart(
                        zone_history[
                            ["elqi"]
                        ]
                    )

                    st.markdown(
                        "**Data Confidence History**"
                    )

                    confidence_history = (
                        zone_history[
                            ["confidence"]
                        ]
                        .copy()
                    )

                    confidence_history[
                        "confidence"
                    ] *= 100

                    st.line_chart(
                        confidence_history
                    )


