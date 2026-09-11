from pathlib import Path

import yaml
from experiments.benchmark_routing import (
    benchmark_minimum_hop
)
from core.network import (
    WirelessSensorNetwork
)
from metrics.evaluator import (
    export_environment_results,
    export_simulation_results
)
from simulation.simulator import (
    WSNSimulator
)
from topology.deployment import (
    create_sink,
    deploy_sensors
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

    max_rounds = (
        config["simulation"][
            "max_rounds"
        ]
    )

    print(
        "Simulation started..."
    )

    for _ in range(max_rounds):

        simulator.run_round()

        if (
            simulator.current_round
            % 100 == 0
        ):

            metrics = (
                simulator.get_metrics()
            )

            print(
                f"Round "
                f"{metrics['round']:5d} | "
                f"Alive "
                f"{metrics['alive_nodes']:3d} | "
                f"PDR "
                f"{metrics['pdr'] * 100:6.2f}% | "
                f"Energy "
                f"{metrics['total_remaining_energy_j']:.2f} J"
            )

        if simulator.lnd_round is not None:
            break

    simulator.print_summary()

    export_simulation_results(
        simulator
    )

    export_environment_results(
        simulator
    )


    plot_alive_nodes(
        simulator.history
    )

    plot_remaining_energy(
        simulator.history
    )

    plot_pdr(
        simulator.history
    )

    plot_throughput(
        simulator.history
    )

    result = benchmark_minimum_hop(network)
    print(result)


if __name__ == "__main__":
    main()