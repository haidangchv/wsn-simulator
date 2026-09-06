from time import perf_counter

from routing.minimum_hop import (
    find_minimum_hop_route
)

from routing.route_table import (
    build_minimum_hop_route_table
)


def benchmark_minimum_hop(
    network
):

    sensor_ids = [
        sensor.node_id
        for sensor
        in network.sensors
    ]

    # ----------------------------------
    # Old approach
    # ----------------------------------

    start = perf_counter()

    for sensor_id in sensor_ids:

        find_minimum_hop_route(
            graph=network.graph,

            source_id=sensor_id,

            sink_id=(
                network.sink.node_id
            )
        )

    old_time = (
        perf_counter()
        - start
    )

    # ----------------------------------
    # Route-table approach
    # ----------------------------------

    start = perf_counter()

    build_minimum_hop_route_table(
        graph=network.graph,

        sensor_ids=sensor_ids,

        sink_id=(
            network.sink.node_id
        )
    )

    new_time = (
        perf_counter()
        - start
    )

    if new_time > 0:

        speedup = (
            old_time
            / new_time
        )

    else:

        speedup = float(
            "inf"
        )

    return {
        "individual_bfs_seconds":
            old_time,

        "route_table_seconds":
            new_time,

        "speedup":
            speedup
    }
    
