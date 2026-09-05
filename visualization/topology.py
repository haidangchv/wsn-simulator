from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import networkx as nx
from core.sensor import SensorNode
from core.sink import SinkNode


def plot_network(
    sensors: List[SensorNode],
    sink: SinkNode,
    config: dict,
    show: bool = True,
    save: bool = True
):

    fig, ax = plt.subplots(
        figsize=(10, 10)
    )

    sensor_types = sorted(
        set(
            sensor.sensor_type
            for sensor in sensors
        )
    )

    for sensor_type in sensor_types:

        group = [
            sensor
            for sensor in sensors
            if sensor.sensor_type == sensor_type
        ]

        x = [
            sensor.x
            for sensor in group
        ]

        y = [
            sensor.y
            for sensor in group
        ]

        ax.scatter(
            x,
            y,
            s=20,
            alpha=0.7,
            label=sensor_type
        )

    ax.scatter(
        sink.x,
        sink.y,
        marker="*",
        s=250,
        label="Sink",
        edgecolors="black"
    )

    width = config["network"]["width_m"]
    height = config["network"]["height_m"]

    ax.set_xlim(0, width)
    ax.set_ylim(0, height)

    ax.set_xlabel("X (meters)")
    ax.set_ylabel("Y (meters)")

    ax.set_title(
        "Wireless Sensor Network Deployment"
    )

    ax.grid(
        True,
        alpha=0.25
    )

    ax.legend()

    ax.set_aspect(
        "equal",
        adjustable="box"
    )

    plt.tight_layout()

    if save:

        output_dir = Path("outputs")

        output_dir.mkdir(
            exist_ok=True
        )

        output_path = (
            output_dir
            / "network_topology.png"
        )

        plt.savefig(
            output_path,
            dpi=200
        )

        print(
            f"Topology saved to: "
            f"{output_path}"
        )

    if show:
        plt.show()

    else:
        plt.close(fig)

def plot_neighbor_graph(
    sensors,
    sink,
    graph: nx.Graph,
    config: dict,
    show: bool = True,
    save: bool = True
):

    fig, ax = plt.subplots(
        figsize=(10, 10)
    )

    sensor_map = {
        sensor.node_id: sensor
        for sensor in sensors
    }

    # Draw communication links first
    for node_a, node_b in graph.edges():

        if node_a == sink.node_id:

            x1 = sink.x
            y1 = sink.y

        else:

            x1 = sensor_map[node_a].x
            y1 = sensor_map[node_a].y

        if node_b == sink.node_id:

            x2 = sink.x
            y2 = sink.y

        else:

            x2 = sensor_map[node_b].x
            y2 = sensor_map[node_b].y

        ax.plot(
            [x1, x2],
            [y1, y2],
            linewidth=0.4,
            alpha=0.15
        )

    # Draw sensors
    sensor_types = sorted(
        set(
            sensor.sensor_type
            for sensor in sensors
        )
    )

    for sensor_type in sensor_types:

        group = [
            sensor
            for sensor in sensors
            if sensor.sensor_type == sensor_type
        ]

        ax.scatter(
            [sensor.x for sensor in group],
            [sensor.y for sensor in group],
            s=18,
            alpha=0.8,
            label=sensor_type
        )

    # Draw sink
    ax.scatter(
        sink.x,
        sink.y,
        marker="*",
        s=250,
        edgecolors="black",
        label="Sink"
    )

    width = config["network"]["width_m"]
    height = config["network"]["height_m"]

    ax.set_xlim(
        0,
        width
    )

    ax.set_ylim(
        0,
        height
    )

    ax.set_xlabel(
        "X (meters)"
    )

    ax.set_ylabel(
        "Y (meters)"
    )

    ax.set_title(
        "WSN Neighbor Graph"
    )

    ax.set_aspect(
        "equal",
        adjustable="box"
    )

    ax.grid(
        True,
        alpha=0.2
    )

    ax.legend()

    plt.tight_layout()

    if save:

        output_dir = Path("outputs")

        output_dir.mkdir(
            exist_ok=True
        )

        output_path = (
            output_dir
            / "neighbor_graph.png"
        )

        plt.savefig(
            output_path,
            dpi=200
        )

        print(
            f"Neighbor graph saved to: "
            f"{output_path}"
        )

    if show:
        plt.show()

    else:
        plt.close(fig)

def plot_route(
    sensors,
    sink,
    graph,
    route,
    config: dict,
    show: bool = True,
    save: bool = True
):

    if route is None:
        print(
            "Cannot plot route: "
            "route does not exist."
        )
        return

    fig, ax = plt.subplots(
        figsize=(10, 10)
    )

    sensor_map = {
        sensor.node_id: sensor
        for sensor in sensors
    }

    # Background links
    for node_a, node_b in graph.edges():

        if node_a == sink.node_id:

            x1, y1 = sink.x, sink.y

        else:

            sensor_a = sensor_map[node_a]

            x1, y1 = (
                sensor_a.x,
                sensor_a.y
            )

        if node_b == sink.node_id:

            x2, y2 = sink.x, sink.y

        else:

            sensor_b = sensor_map[node_b]

            x2, y2 = (
                sensor_b.x,
                sensor_b.y
            )

        ax.plot(
            [x1, x2],
            [y1, y2],
            linewidth=0.25,
            alpha=0.06
        )
    
    # All sensors
    ax.scatter(
        [sensor.x for sensor in sensors],
        [sensor.y for sensor in sensors],
        s=12,
        alpha=0.35,
        label="Sensors"
    )

    # Route positions
    route_x = []
    route_y = []

    for node_id in route.path:

        if node_id == sink.node_id:

            route_x.append(sink.x)
            route_y.append(sink.y)

        else:

            sensor = sensor_map[node_id]

            route_x.append(sensor.x)
            route_y.append(sensor.y)

    # Highlight route
    ax.plot(
        route_x,
        route_y,
        linewidth=3,
        marker="o",
        markersize=6,
        label="Minimum-Hop Route"
    )

    # Sink
    ax.scatter(
        sink.x,
        sink.y,
        marker="*",
        s=280,
        edgecolors="black",
        label="Sink"
    )

    # Source
    source_id = route.path[0]

    if source_id != sink.node_id:

        source = sensor_map[source_id]

        ax.scatter(
            source.x,
            source.y,
            marker="s",
            s=100,
            edgecolors="black",
            label=f"Source {source_id}"
        )

    width = config["network"]["width_m"]
    height = config["network"]["height_m"]

    ax.set_xlim(
        0,
        width
    )

    ax.set_ylim(
        0,
        height
    )

    ax.set_xlabel(
        "X (meters)"
    )

    ax.set_ylabel(
        "Y (meters)"
    )

    ax.set_title(
        f"Minimum-Hop Route "
        f"(Sensor {source_id} -> Sink)"
    )

    ax.grid(
        True,
        alpha=0.2
    )

    ax.set_aspect(
        "equal",
        adjustable="box"
    )

    ax.legend()

    plt.tight_layout()

    for node_id, x, y in zip(
        route.path,
        route_x,
        route_y
    ):

        ax.annotate(
            str(node_id),
            (x, y),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8
        )
        
    if save:

        output_dir = Path(
            "outputs"
        )

        output_dir.mkdir(
            exist_ok=True
        )

        output_path = (
            output_dir
            /
            f"minimum_hop_route_"
            f"sensor_{source_id}.png"
        )

        plt.savefig(
            output_path,
            dpi=200
        )

        print(
            "Route visualization saved to: "
            f"{output_path}"
        )

    if show:
        plt.show()

    else:
        plt.close(fig)