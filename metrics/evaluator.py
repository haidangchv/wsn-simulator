from pathlib import Path

import pandas as pd

from environment.degradation import (
    calculate_zone_degradation
)



def history_dataframe(
    simulator
) -> pd.DataFrame:
    """
    Convert round history to DataFrame.
    """

    return pd.DataFrame(
        simulator.history
    )


def node_dataframe(
    simulator
) -> pd.DataFrame:
    """
    Create final per-node statistics.
    """

    records = []

    for sensor in (
        simulator.network.sensors
    ):

        records.append({
            "node_id":
                sensor.node_id,

            "sensor_type":
                sensor.sensor_type,

            "x":
                sensor.x,

            "y":
                sensor.y,

            "initial_energy_j":
                sensor.initial_energy,

            "remaining_energy_j":
                sensor.remaining_energy,

            "consumed_energy_j":
                sensor.consumed_energy_j,

            "state":
                sensor.state,

            "relay_enabled":
                sensor.relay_enabled,

            "generated_packets":
                sensor.generated_packets,

            "sent_packets":
                sensor.sent_packets,

            "received_packets":
                sensor.received_packets,

            "forwarded_packets":
                sensor.forwarded_packets,

            "death_round":
                sensor.death_round,

            "transmitted_bytes":
                sensor.transmitted_bytes,

            "received_bytes":
                sensor.received_bytes,

            "forwarded_bytes":
                sensor.forwarded_bytes
        })

    return pd.DataFrame(
        records
    )


def summary_dataframe(
    simulator
) -> pd.DataFrame:

    return pd.DataFrame([
        simulator.get_metrics()
    ])


def export_simulation_results(
    simulator,
    output_dir: str = "outputs/results"
) -> dict:

    output_path = Path(
        output_dir
    )

    output_path.mkdir(
        parents=True,
        exist_ok=True
    )

    history_path = (
        output_path
        / "round_history.csv"
    )

    nodes_path = (
        output_path
        / "node_results.csv"
    )

    summary_path = (
        output_path
        / "summary.csv"
    )

    history_dataframe(
        simulator
    ).to_csv(
        history_path,
        index=False
    )

    node_dataframe(
        simulator
    ).to_csv(
        nodes_path,
        index=False
    )

    summary_dataframe(
        simulator
    ).to_csv(
        summary_path,
        index=False
    )

    return {
        "history":
            history_path,

        "nodes":
            nodes_path,

        "summary":
            summary_path
    }


def export_environment_results(
    simulator,
    output_dir: str = "outputs/results"
) -> dict:

    output_path = Path(
        output_dir
    )

    output_path.mkdir(
        parents=True,
        exist_ok=True
    )

    paths = {}

    collector = (
        simulator.environment_collector
    )

    if collector is not None:

        generated_path = (
            output_path
            /
            "environment_generated.csv"
        )

        received_path = (
            output_path
            /
            "environment_received.csv"
        )

        collector.generated_dataframe().to_csv(
            generated_path,
            index=False
        )

        collector.received_dataframe().to_csv(
            received_path,
            index=False
        )

        paths[
            "environment_generated"
        ] = generated_path

        paths[
            "environment_received"
        ] = received_path

    tracker = (
        simulator.zone_history_tracker
    )

    if tracker is not None:

        history = (
            tracker.dataframe()
        )

        if not history.empty:

            zone_history_path = (
                output_path
                /
                "zone_elqi_history.csv"
            )

            history.to_csv(
                zone_history_path,
                index=False
            )

            paths[
                "zone_elqi_history"
            ] = (
                zone_history_path
            )

            degradation = (
                calculate_zone_degradation(
                    history_dataframe=history,

                    config=(
                        simulator.config
                    ),

                    current_round=(
                        simulator.current_round
                    )
                )
            )

            if not degradation.empty:

                degradation_path = (
                    output_path
                    /
                    "zone_degradation.csv"
                )

                degradation.to_csv(
                    degradation_path,
                    index=False
                )

                paths[
                    "zone_degradation"
                ] = degradation_path

    return paths
 