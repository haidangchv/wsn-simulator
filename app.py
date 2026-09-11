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
        max_value=20.0,
        value=float(
            current_config[
                "sensor"
            ][
                "initial_energy_j"
            ]
        ),
        step=0.1
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

    st.rerun()


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

st.sidebar.divider()

st.sidebar.subheader(
    "🧭 Routing"
)

routing_options = {
    "Minimum-Hop BFS":
        "minimum_hop",

    "ECMHR":
        "ecmhr"
}

current_algorithm = getattr(
    simulator,
    "routing_algorithm",
    "minimum_hop"
)

current_label = next(
    (
        label
        for label, value
        in routing_options.items()
        if value == current_algorithm
    ),
    "Minimum-Hop BFS"
)

selected_label = (
    st.sidebar.selectbox(
        "Routing Algorithm",
        options=list(
            routing_options.keys()
        ),
        index=list(
            routing_options.keys()
        ).index(
            current_label
        )
    )
)

selected_algorithm = (
    routing_options[
        selected_label
    ]
)

if (
    selected_algorithm
    != getattr(simulator, "routing_algorithm", None)
):

    if hasattr(simulator, "set_routing_algorithm"):
        simulator.set_routing_algorithm(
            selected_algorithm
        )
    else:
        simulator.routing_algorithm = (
            selected_algorithm
        )

    st.session_state.selected_route = (
        None
    )
    st.session_state.find_route_searched = (
        False
    )

if (
    getattr(simulator, "routing_algorithm", "minimum_hop")
    == "ecmhr"
):

    st.sidebar.subheader(
        "🚨 ECMHR Emergency Mode"
    )

    emergency_enabled = (
        st.sidebar.checkbox(
            "Allow Emergency Routing",
            value=getattr(
                simulator,
                "allow_emergency_mode",
                False
            )
        )
    )

    emergency_threshold = (
        st.sidebar.slider(
            "Emergency Threshold (%)",
            min_value=1,
            max_value=19,
            value=int(
                getattr(
                    simulator,
                    "emergency_threshold_ratio",
                    0.10
                )
                * 100
            )
        )
    )

    simulator.allow_emergency_mode = (
        emergency_enabled
    )

    simulator.emergency_threshold_ratio = (
        emergency_threshold / 100
    )

    if hasattr(simulator, "route_manager"):

        simulator.route_manager.allow_emergency_mode = (
            emergency_enabled
        )

        simulator.route_manager.emergency_threshold_ratio = (
            emergency_threshold / 100
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
    "ECMHR"
    if getattr(
        simulator,
        "routing_algorithm",
        "minimum_hop"
    ) == "ecmhr"
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
            "emergency_mode",
            False
        ):
            st.warning(
                "⚠️ No normal ECMHR route was available. "
                "The network is using Emergency Routing."
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

        threshold_used = getattr(
            route,
            "threshold_ratio_used",
            None
        )

        if threshold_used is not None:
            st.caption(
                f"Relay energy threshold used: "
                f"{threshold_used * 100:.0f}%"
            )

        if low_energy_relays and not getattr(route, "emergency_mode", False):
            st.warning(
                f"⚠️ Route traverses {len(low_energy_relays)} LOW_ENERGY relay(s): "
                f"{', '.join(f'Sensor {n}' for n in low_energy_relays)}. "
                "Switch to ECMHR to reroute and protect low-battery nodes!"
            )

        r1, r2, r3 = st.columns(3)

        r1.metric(
            "Hop Count",
            route.hop_count
        )

        r2.metric(
            "Route Distance",
            f"{route.total_distance_m:.2f} m"
        )

        bottleneck_val = getattr(
            route,
            "bottleneck_energy_j",
            None
        )

        if bottleneck_val is not None:
            r3.metric(
                "Bottleneck Energy",
                f"{bottleneck_val:.4f} J"
            )
        else:
            r3.metric(
                "Bottleneck Energy",
                "N/A"
            )

    elif st.session_state.get("find_route_searched", False):

        searched_source = st.session_state.get(
            "last_searched_source",
            selected_source
        )

        if getattr(simulator, "routing_algorithm", "minimum_hop") == "ecmhr":
            st.error(
                f"❌ No valid ECMHR route found for Sensor {searched_source} to Sink! "
                "All relay paths to the Sink are blocked by LOW_ENERGY (≤ 20%) or DEAD nodes."
            )
            if not getattr(simulator, "allow_emergency_mode", False):
                st.info(
                    "💡 Tip: Enable **'Allow Emergency Routing'** in the sidebar to permit routing through relays with lower remaining energy."
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

network_figure = (
    create_network_figure(
        network=network,
        route=route,
        show_edges=show_edges,
        edge_geometry=st.session_state.get(
            "edge_geometry"
        )
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


run1, run10, run50, run_custom = (
    st.columns(4)
)


with run1:

    if st.button(
        "Run 1 Round",
        use_container_width=True
    ):

        with st.spinner(
            "Running 1 simulation round..."
        ):

            simulator.run(
                rounds=1
            )

        st.session_state.selected_route = None
        st.session_state.find_route_searched = False
        st.rerun()


with run10:

    if st.button(
        "Run 10 Rounds",
        use_container_width=True
    ):

        with st.spinner(
            "Running 10 simulation rounds..."
        ):

            simulator.run(
                rounds=10
            )

        st.session_state.selected_route = None
        st.session_state.find_route_searched = False
        st.rerun()


with run50:

    if st.button(
        "Run 50 Rounds",
        use_container_width=True
    ):

        with st.spinner(
            "Running 50 simulation rounds..."
        ):

            simulator.run(
                rounds=50
            )

        st.session_state.selected_route = None
        st.session_state.find_route_searched = False
        st.rerun()


with run_custom:

    custom_rounds = (
        st.number_input(
            "Custom rounds",
            min_value=1,
            max_value=1000,
            value=100,
            step=10
        )
    )

    if st.button(
        "Run Custom",
        use_container_width=True
    ):

        with st.spinner(
            f"Running {custom_rounds} rounds..."
        ):

            simulator.run(
                rounds=int(
                    custom_rounds
                )
            )

        st.session_state.selected_route = None
        st.session_state.find_route_searched = False
        st.rerun()


# =========================================
# CURRENT METRICS
# =========================================

metrics = (
    simulator.get_metrics()
)

st.subheader(
    "📊 Current Metrics"
)

elapsed_seconds = (
    metrics["elapsed_seconds"]
)

st.caption(
    f"Simulation time: "
    f"{elapsed_seconds:.0f} seconds "
    f"({elapsed_seconds / 60:.2f} minutes)"
)


m1, m2, m3, m4 = (
    st.columns(4)
)

m1.metric(
    "Round",
    metrics["round"]
)

m2.metric(
    "Alive",
    metrics["alive_nodes"]
)

m3.metric(
    "Low Energy",
    metrics["low_energy_nodes"]
)

m4.metric(
    "Dead",
    metrics["dead_nodes"]
)


m5, m6, m7, m8 = (
    st.columns(4)
)

m5.metric(
    "PDR",
    f"{metrics['pdr'] * 100:.2f}%"
)

m6.metric(
    "Throughput",
    f"{metrics['throughput_bps'] / 1000:.2f} kbps"
)

m7.metric(
    "Avg Delay",
    f"{metrics['average_delay_ms']:.2f} ms"
)

m8.metric(
    "Avg Hop",
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

    st.info(
        f"First Node Death occurred "
        f"at round "
        f"{metrics['fnd_round']}."
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
        max_value=500,
        value=100,
        step=10
    )
)

if st.button(
    "Compare Minimum-Hop vs ECMHR"
):

    with st.spinner(
        "Running routing comparison..."
    ):

        comparison_df = (
            compare_algorithms(
                config=(
                    st.session_state.config
                ),
                rounds=int(
                    comparison_rounds
                )
            )
        )

    display_columns = [
        "algorithm",
        "alive_nodes",
        "dead_nodes",
        "pdr",
        "average_hop_count",
        "total_energy_consumed_j",
        "energy_efficiency_bits_per_j",
        "fnd_round"
    ]

    st.dataframe(
        comparison_df[
            display_columns
        ],
        use_container_width=True,
        hide_index=True
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
                sensor.received_packets
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
        trend_tab,
        heatmap_tab,
        quality_tab,
        degradation_tab
    ) = st.tabs([
        "📈 Trends",
        "🌡 Heatmaps",
        "🗺 Living Quality",
        "📉 Degradation"
    ])


    with trend_tab:

        environmental_df = (
            collector.received_dataframe()
        )

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


