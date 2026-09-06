from copy import deepcopy
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from core.network import WirelessSensorNetwork
from simulation.simulator import WSNSimulator
from topology.deployment import (
    create_sink,
    deploy_sensors
)

from streamlit_components.network_chart import (
    create_network_figure
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

    if "network" not in st.session_state:

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

    if "selected_route" not in (
        st.session_state
    ):

        st.session_state.selected_route = (
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

    st.session_state.selected_route = (
        None
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

    st.session_state.selected_route = (
        None
    )

    st.rerun()


network = (
    st.session_state.network
)

simulator = (
    st.session_state.simulator
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

st.subheader(
    "🧭 Minimum-Hop Routing"
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

    selected_source = st.selectbox(
        "Source Sensor",
        sensor_ids
    )

    if st.button(
        "Find Route",
        use_container_width=True
    ):

        st.session_state.selected_route = (
            simulator.find_current_route(
                selected_source
            )
        )


route = (
    st.session_state.selected_route
)


with route_col2:

    if route is not None:

        st.success(
            " → ".join(
                str(node)
                for node in route.path
            )
        )

        r1, r2 = st.columns(2)

        r1.metric(
            "Hop Count",
            route.hop_count
        )

        r2.metric(
            "Route Distance",
            f"{route.total_distance_m:.2f} m"
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
        show_edges=show_edges
    )
)

st.plotly_chart(
    network_figure,
    use_container_width=True
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