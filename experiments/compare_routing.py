from copy import deepcopy

import pandas as pd

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


def run_one_algorithm(
    config: dict,
    algorithm: str,
    rounds: int
) -> dict:

    experiment_config = (
        deepcopy(config)
    )

    sensors = deploy_sensors(
        experiment_config
    )

    sink = create_sink(
        experiment_config
    )

    network = WirelessSensorNetwork(
        sensors=sensors,
        sink=sink
    )

    network.build_topology()

    simulator = WSNSimulator(
        network=network,
        config=experiment_config,
        routing_algorithm=algorithm
    )

    simulator.run(
        rounds=rounds
    )

    metrics = (
        simulator.get_metrics()
        .copy()
    )

    metrics[
        "algorithm"
    ] = algorithm

    return metrics


def compare_algorithms(
    config: dict,
    rounds: int = 100
) -> pd.DataFrame:

    results = []

    for algorithm in [
        "minimum_hop",
        "ecmhr"
    ]:

        metrics = (
            run_one_algorithm(
                config=config,
                algorithm=algorithm,
                rounds=rounds
            )
        )

        results.append(
            metrics
        )

    return pd.DataFrame(
        results
    )