from math import degrees
from collections import Counter
from pathlib import Path
from visualization.topology import (
    plot_network,
    plot_neighbor_graph
)
from core.network import WirelessSensorNetwork
import yaml

from topology.deployment import (
    create_sink,
    deploy_sensors,
)

def load_config():
    config_path = Path(__file__).parent / "config.yaml"

    with open(config_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def main():

    config = load_config()

    print("=== WSN Simulator ===")

    sensors = deploy_sensors(config)
    sink = create_sink(config)
    network = WirelessSensorNetwork(
        sensors=sensors,
        sink=sink
    )

    network.build_topology()
    print()
    print("=== Network Topology ===")

    stats = network.get_statistics()

    print(
        f"Total graph nodes: "
        f"{stats['num_nodes_total']}"
    )

    print(
        f"Total edges: "
        f"{stats['num_edges']}"
    )

    print(
        f"Connected to sink: "
        f"{stats['connected_to_sink']} "
        f"/ {stats['num_sensors']}"
    )

    print(
        f"Disconnected from sink: "
        f"{stats['disconnected_from_sink']}"
    )

    print(
        f"Isolated sensors: "
        f"{stats['isolated_sensors']}"
    )

    print(
        f"Direct sink neighbors: "
        f"{stats['direct_sink_neighbors']}"
    )

    print(
        f"Average sensor degree: "
        f"{stats['average_sensor_degree']:.2f}"
    )

    print(
        f"Connectivity ratio: "
        f"{stats['connectivity_ratio'] * 100:.2f}%"
    )

    print("=== Neighbor Examples ===")

    for sensor in sensors[:10]:

        print(
            f"Sensor {sensor.node_id}: "
            f"{len(sensor.neighbors)} neighbors"
        )

        print(
            f"    {sensor.neighbors}"
        )

    print()
    print("=== Network ===")

    print(f"Number of sensors: {len(sensors)}")
    print(f"Sink: {sink}")

    print()
    print("=== Sensor Types ===")

    type_counter = Counter(
        sensor.sensor_type
        for sensor in sensors
    )

    for sensor_type, quantity in type_counter.items():
        print(
            f"{sensor_type}: "
            f"{quantity}"
        )

    print()
    print("=== First 10 Sensors ===")

    for sensor in sensors[:10]:
        print(sensor)

    print()
    print("=== Visualization ===")

    plot_network(
        sensors=sensors,
        sink=sink,
        config=config
    )
    print()
    print("=== Neighbor Graph Visualization ===")

    plot_neighbor_graph(
        sensors=sensors,
        sink=sink,
        graph=network.graph,
        config=config
    )

    degrees = [
    network.graph.degree(sensor.node_id)
    for sensor in sensors
]

    print()
    print("=== Degree Statistics ===")

    print(
        f"Minimum degree: "
        f"{min(degrees)}"
    )

    print(
        f"Maximum degree: "
        f"{max(degrees)}"
    )

    print(
        f"Average degree: "
        f"{sum(degrees) / len(degrees):.2f}"
    )
    
if __name__ == "__main__":
    main()