from pathlib import Path

import yaml
from metrics.evaluator import (
    export_simulation_results
)
from core.network import (
    WirelessSensorNetwork
)
from topology.deployment import (
    create_sink,
    deploy_sensors
)
from simulation.simulator import (
    WSNSimulator
)
from visualization.energy import (
    plot_alive_nodes,
    plot_pdr,
    plot_remaining_energy,
    plot_throughput
)


def load_config():

    path = (
        Path(__file__).parent
        / "config.yaml"
    )

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        return yaml.safe_load(file)


def main():

    config = load_config()

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

    simulator.set_routing_algorithm(
        "ecmhr"
    )

    source_id = 1

    route_before = (
        simulator.find_current_route(
            source_id
        )
    )

    print(
        "Route before:",
        route_before
    )

    if (
        route_before is not None
        and
        len(route_before.path) > 2
    ):

        relay_id = (
            route_before.path[1]
        )

        relay = (
            network.get_sensor(
                relay_id
            )
        )

        relay.remaining_energy = 0.30

        relay.update_state(
            config["sensor"][
                "energy_threshold_ratio"
            ]
        )

        print(
            f"Forced Sensor {relay_id} "
            f"to LOW_ENERGY"
        )

        route_after = (
            simulator.find_current_route(
                source_id
            )
        )

        print(
            "Route after:",
            route_after
        )
    


if __name__ == "__main__":
    main()