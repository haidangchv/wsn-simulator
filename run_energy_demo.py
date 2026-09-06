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

    simulator.run(
        rounds=100
    )

    simulator.print_summary()
    paths = export_simulation_results(simulator)
    print()
    print("Results exported:")

    for name, path in paths.items():

        print(
            f"{name}: {path}"
        )
    history = simulator.history

    plot_alive_nodes(
        history,
        show=True,
        save=True
    )

    plot_remaining_energy(
        history,
        show=True,
        save=True
    )

    plot_pdr(
        history,
        show=True,
        save=True
    )

    plot_throughput(
        history,
        show=True,
        save=True
    )
    


if __name__ == "__main__":
    main()