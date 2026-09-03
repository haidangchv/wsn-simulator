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