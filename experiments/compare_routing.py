from copy import deepcopy
from typing import Optional, List, Dict, Any, Tuple
import pandas as pd

from core.network import WirelessSensorNetwork
from simulation.simulator import WSNSimulator
from topology.deployment import create_sink, deploy_sensors


def run_one_algorithm(
    config: dict,
    algorithm: str,
    rounds: int,
    return_simulator: bool = False,
    mobile_sink_enabled: Optional[bool] = None
):
    if algorithm == "lb_ecmhr":
        algorithm = "ecmhr"

    experiment_config = deepcopy(config)

    if mobile_sink_enabled is not None:
        if "mobile_sink" not in experiment_config:
            experiment_config["mobile_sink"] = {}
        experiment_config["mobile_sink"]["enabled"] = mobile_sink_enabled

    sensors = deploy_sensors(experiment_config)
    sink = create_sink(experiment_config)
    network = WirelessSensorNetwork(sensors=sensors, sink=sink)
    network.build_topology()

    simulator = WSNSimulator(
        network=network,
        config=experiment_config,
        routing_algorithm=algorithm
    )

    simulator.run(rounds=rounds)

    metrics = simulator.get_metrics().copy()
    metrics["algorithm"] = algorithm
    metrics["mobile_sink_enabled"] = simulator.mobile_sink_enabled

    if return_simulator:
        return metrics, simulator

    return metrics


def compare_algorithms(
    config: dict,
    rounds: int = 100,
    return_history: bool = False,
    algorithms: Optional[List[str]] = None
):
    results = []
    history_data = {}

    target_algorithms = algorithms or [
        "minimum_hop",
        "ecmhr"
    ]

    for algorithm in target_algorithms:
        algo_name = "ecmhr" if algorithm == "lb_ecmhr" else algorithm
        metrics, simulator = run_one_algorithm(
            config=config,
            algorithm=algo_name,
            rounds=rounds,
            return_simulator=True
        )

        results.append(metrics)
        history_data[algo_name] = {
            "metrics": metrics,
            "history": simulator.history,
            "fnd_round": simulator.fnd_round,
            "total_nodes": len(simulator.network.sensors)
        }

    df = pd.DataFrame(results)

    if return_history:
        return df, history_data

    return df


def compare_sink_mobility(
    config: dict,
    rounds: int = 100,
    algorithm: str = "ecmhr",
    return_history: bool = False
):
    """
    So sánh hiệu quả giữa Sink Cố định (Fixed Sink) và Sink Thích ứng (Adaptive Mobile Sink).
    """
    results = []
    history_data = {}

    for is_mobile, label in [(False, "Fixed Sink"), (True, "Adaptive Mobile Sink")]:
        metrics, simulator = run_one_algorithm(
            config=config,
            algorithm=algorithm,
            rounds=rounds,
            return_simulator=True,
            mobile_sink_enabled=is_mobile
        )
        metrics["sink_mode"] = label
        results.append(metrics)
        history_data[label] = {
            "metrics": metrics,
            "history": simulator.history,
            "fnd_round": simulator.fnd_round,
            "total_nodes": len(simulator.network.sensors)
        }

    df = pd.DataFrame(results)
    if return_history:
        return df, history_data
    return df