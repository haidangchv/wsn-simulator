from pathlib import Path

import yaml

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

    while (
        simulator.fnd_round is None
        and
        simulator.current_round
        < max_rounds
    ):

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
                f"{simulator.current_round}: "
                f"Alive="
                f"{metrics['alive_nodes']}"
            )

    print(
        "FND:",
        simulator.fnd_round
    )

    dead_nodes = [
        sensor
        for sensor in sensors
        if not sensor.is_alive()
    ]

    print(
        "Dead sensors:"
    )

    for sensor in dead_nodes:

        print(
            sensor.node_id,
            sensor.x,
            sensor.y,
            sensor.consumed_energy_j
        )


if __name__ == "__main__":
    main()