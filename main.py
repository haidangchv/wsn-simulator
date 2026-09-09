from math import degrees
from collections import Counter
from pathlib import Path
from visualization.topology import (
    plot_network,
    plot_neighbor_graph,
    plot_route
)
from visualization.routing import (
    plot_hop_distribution
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
    
    print()
    print("=== Minimum-Hop Routing ===")

    source_sensor_id = 1

    route = network.find_minimum_hop_route(
        source_sensor_id
    )

    if route is None:

        print(
            f"Sensor {source_sensor_id} "
            f"has no route to sink."
        )
    else:
        plot_route(
            sensors=sensors,
            sink=sink,
            graph=network.graph,
            route=route,
            config=config
        )
        print(
            f"Source sensor: "
            f"{source_sensor_id}"
        )

        print(
            "Route: "
            +
            " -> ".join(
                str(node)
                for node in route.path
            )
        )

        print(
            f"Hop count: "
            f"{route.hop_count}"
        )

        print(
            f"Total distance: "
            f"{route.total_distance_m:.2f} m"
        )

    print()

    all_routes = (
        network.find_all_minimum_hop_routes()
    )

    valid_routes = {
        sensor_id: route
        for sensor_id, route
        in all_routes.items()
        if route is not None
    }

    farthest_sensor_id = max(
        valid_routes,
        key=lambda sensor_id:
            valid_routes[
                sensor_id
            ].hop_count
    )

    farthest_route = (
        valid_routes[
            farthest_sensor_id
        ]
    )
    plot_route(
        sensors=sensors,
        sink=sink,
        graph=network.graph,
        route=farthest_route,
        config=config
    )
    print()
    print("=== Maximum-Hop Sensor ===")

    print(
        f"Sensor: "
        f"{farthest_sensor_id}"
    )

    print(
        f"Hop count: "
        f"{farthest_route.hop_count}"
    )

    print(
        "Route: "
        +
        " -> ".join(
            str(node)
            for node in farthest_route.path
        )
    )

    print("=== Global Routing Statistics ===")

    routing_stats = (
        network.minimum_hop_statistics()
    )

    print(
        f"Routable sensors: "
        f"{routing_stats['routable_sensors']}"
    )

    print(
        f"Unroutable sensors: "
        f"{routing_stats['unroutable_sensors']}"
    )

    print(
        f"Minimum hop count: "
        f"{routing_stats['minimum_hops']}"
    )

    print(
        f"Maximum hop count: "
        f"{routing_stats['maximum_hops']}"
    )

    if routing_stats["average_hops"] is not None:

        print(
            f"Average hop count: "
            f"{routing_stats['average_hops']:.2f}"
        )

    if (
        routing_stats["average_distance_m"]
        is not None
    ):

        print(
            f"Average route distance: "
            f"{routing_stats['average_distance_m']:.2f} m"
        )

    plot_hop_distribution(
        routes=all_routes
    )

if __name__ == "__main__":
    main()