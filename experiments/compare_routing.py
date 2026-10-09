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
    rounds: int,
    return_simulator: bool = False
):

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

    if return_simulator:
        return metrics, simulator

    return metrics


def compare_algorithms(
    config: dict,
    rounds: int = 100,
    return_history: bool = False
):

    results = []
    history_data = {}

    for algorithm in [
        "minimum_hop",
        "lb_ecmhr"
    ]:

        metrics, simulator = (
            run_one_algorithm(
                config=config,
                algorithm=algorithm,
                rounds=rounds,
                return_simulator=True
            )
        )

        results.append(
            metrics
        )

        history_data[algorithm] = {
            "metrics": metrics,
            "history": simulator.history,
            "fnd_round": simulator.fnd_round,
            "total_nodes": len(simulator.network.sensors)
        }

    df = pd.DataFrame(
        results
    )

    if return_history:
        return df, history_data

    return df