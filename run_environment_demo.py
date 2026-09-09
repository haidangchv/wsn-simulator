from pathlib import Path

import yaml

from core.network import (
    WirelessSensorNetwork
)

from simulation.simulator import (
    WSNSimulator
)

from topology.deployment import (
    create_sink,
    deploy_sensors
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

        return yaml.safe_load(
            file
        )


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
        config=config,
        routing_algorithm="ecmhr"
    )

    simulator.run(
        rounds=10
    )

    collector = (
        simulator.environment_collector
    )

    received = (
        collector.received_dataframe()
    )

    print()
    print(
        "=== ENVIRONMENTAL DATA ==="
    )

    print(
        received.head(20)
    )

    print()
    print(
        "Received measurements:",
        len(received)
    )

    print()
    print(
        "Sensor types:"
    )

    print(
        received[
            "sensor_type"
        ].value_counts()
    )

    for sensor_type in [
        "temperature",
        "humidity",
        "pm25",
        "wind",
        "water_quality"
    ]:

        subset = (
            received[
                received[
                    "sensor_type"
                ]
                ==
                sensor_type
            ]
        )

        print()
        print(
            sensor_type
        )

        print(
            "Min:",
            subset["value"].min()
        )

        print(
            "Mean:",
            round(subset["value"].mean(), 3)
        )

        print(
            "Max:",
            subset["value"].max()
        )


if __name__ == "__main__":
    main()