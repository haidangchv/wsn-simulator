from dataclasses import dataclass
import math

import networkx as nx


@dataclass
class LBECMHRRouteResult:

    path: list

    hop_count: int

    total_distance_m: float

    bottleneck_energy_j: float

    max_relay_load: float

    baseline_hop_count: int

    detour_hops: int

    used_overload_fallback: bool


@dataclass
class _PathLabel:

    path: list

    hop_count: int

    total_distance_m: float

    bottleneck_energy_j: float

    max_relay_load: float


class LBECMHRRouter:
    """
    Load-Balanced Energy-Constrained
    Minimum-Hop Routing.

    Priority:
    1. Relay energy > threshold
    2. Avoid overloaded relays
    3. Minimum hop
    4. Minimum maximum relay load
    5. Maximum bottleneck residual energy
    6. Minimum physical distance

    Preferred route may use at most:
        H_min + max_extra_hops

    Otherwise fallback to the normal
    energy-eligible graph.
    """

    def __init__(
        self,
        network,
        energy_threshold_ratio: float,
        max_extra_hops: int = 1,
        allow_overload_fallback: bool = True
    ):

        self.network = network

        self.graph = network.graph

        self.sink = network.sink

        self.sink_id = (
            network.sink.node_id
        )

        self.sensor_map = {
            sensor.node_id: sensor
            for sensor
            in network.sensors
        }

        self.energy_threshold_ratio = float(
            energy_threshold_ratio
        )

        self.max_extra_hops = int(
            max_extra_hops
        )

        self.allow_overload_fallback = bool(
            allow_overload_fallback
        )

    # ==================================================
    # Geometry
    # ==================================================

    def _node_xy(
        self,
        node_id
    ):

        if node_id == self.sink_id:

            return (
                self.sink.x,
                self.sink.y
            )

        sensor = (
            self.sensor_map[
                node_id
            ]
        )

        return (
            sensor.x,
            sensor.y
        )

    def _distance(
        self,
        node_a,
        node_b
    ) -> float:

        ax, ay = self._node_xy(
            node_a
        )

        bx, by = self._node_xy(
            node_b
        )

        return math.hypot(
            ax - bx,
            ay - by
        )

    # ==================================================
    # Relay eligibility
    # ==================================================

    def _is_energy_eligible(
        self,
        node_id
    ) -> bool:

        if node_id == self.sink_id:
            return True

        sensor = (
            self.sensor_map[
                node_id
            ]
        )

        return (
            sensor.is_alive()
            and
            sensor.energy_ratio()
            >
            self.energy_threshold_ratio
        )

    def _build_relay_graph(
        self,
        overloaded_nodes=None,
        exclude_overloaded=False
    ):

        overloaded_nodes = (
            overloaded_nodes
            or set()
        )

        eligible = {
            self.sink_id
        }

        for sensor in (
            self.network.sensors
        ):

            node_id = sensor.node_id

            if not self._is_energy_eligible(
                node_id
            ):

                continue

            if (
                exclude_overloaded
                and
                node_id
                in overloaded_nodes
            ):

                continue

            eligible.add(
                node_id
            )

        return (
            self.graph
            .subgraph(
                eligible
            )
            .copy()
        )

    # ==================================================
    # Dynamic programming labels from Sink
    # ==================================================

    def _build_labels(
        self,
        relay_graph,
        load_factors
    ):

        if (
            self.sink_id
            not in relay_graph
        ):

            return {}, {}

        distances = (
            nx.single_source_shortest_path_length(
                relay_graph,
                self.sink_id
            )
        )

        labels = {
            self.sink_id:
                _PathLabel(
                    path=[
                        self.sink_id
                    ],

                    hop_count=0,

                    total_distance_m=0.0,

                    bottleneck_energy_j=(
                        float("inf")
                    ),

                    max_relay_load=0.0
                )
        }

        ordered_nodes = sorted(
            (
                node_id
                for node_id
                in distances
                if node_id
                !=
                self.sink_id
            ),

            key=lambda node_id:
                distances[node_id]
        )

        for node_id in ordered_nodes:

            node_distance = (
                distances[
                    node_id
                ]
            )

            sensor = (
                self.sensor_map[
                    node_id
                ]
            )

            node_load = float(
                load_factors.get(
                    node_id,
                    0.0
                )
            )

            candidates = []

            for neighbor in (
                relay_graph.neighbors(
                    node_id
                )
            ):

                if (
                    neighbor
                    not in distances
                ):
                    continue

                if (
                    distances[
                        neighbor
                    ]
                    !=
                    node_distance - 1
                ):
                    continue

                if neighbor not in labels:
                    continue

                next_label = (
                    labels[
                        neighbor
                    ]
                )

                total_distance = (
                    self._distance(
                        node_id,
                        neighbor
                    )
                    +
                    next_label
                    .total_distance_m
                )

                max_load = max(
                    node_load,
                    next_label
                    .max_relay_load
                )

                bottleneck = min(
                    sensor.remaining_energy,
                    next_label
                    .bottleneck_energy_j
                )

                label = _PathLabel(

                    path=(
                        [node_id]
                        +
                        next_label.path
                    ),

                    hop_count=(
                        1
                        +
                        next_label.hop_count
                    ),

                    total_distance_m=(
                        total_distance
                    ),

                    bottleneck_energy_j=(
                        bottleneck
                    ),

                    max_relay_load=(
                        max_load
                    )
                )

                score = (
                    label.hop_count,

                    label.max_relay_load,

                    -label.bottleneck_energy_j,

                    label.total_distance_m
                )

                candidates.append(
                    (
                        score,
                        label
                    )
                )

            if candidates:

                candidates.sort(
                    key=lambda item:
                        item[0]
                )

                labels[
                    node_id
                ] = (
                    candidates[0][1]
                )

        return (
            distances,
            labels
        )

    # ==================================================
    # Source may itself be LOW_ENERGY or overloaded.
    # Source can still originate its own packet.
    # ==================================================

    def _route_source(
        self,
        source_id,
        relay_graph,
        labels
    ):

        source = (
            self.sensor_map[
                source_id
            ]
        )

        if not source.is_alive():
            return None

        candidates = []

        # Source is NOT required to belong
        # to relay_graph.
        for neighbor in (
            self.graph.neighbors(
                source_id
            )
        ):

            if neighbor not in relay_graph:
                continue

            if neighbor not in labels:
                continue

            next_label = (
                labels[
                    neighbor
                ]
            )

            hop_count = (
                1
                +
                next_label.hop_count
            )

            total_distance = (
                self._distance(
                    source_id,
                    neighbor
                )
                +
                next_label
                .total_distance_m
            )

            # Source itself is not counted
            # as a relay.
            max_load = (
                next_label
                .max_relay_load
            )

            bottleneck = (
                next_label
                .bottleneck_energy_j
            )

            if math.isinf(
                bottleneck
            ):

                # Direct Source -> Sink
                bottleneck = (
                    source.remaining_energy
                )

            result = LBECMHRRouteResult(

                path=(
                    [source_id]
                    +
                    next_label.path
                ),

                hop_count=(
                    hop_count
                ),

                total_distance_m=(
                    total_distance
                ),

                bottleneck_energy_j=(
                    bottleneck
                ),

                max_relay_load=(
                    max_load
                ),

                baseline_hop_count=(
                    hop_count
                ),

                detour_hops=0,

                used_overload_fallback=False
            )

            score = (
                result.hop_count,

                result.max_relay_load,

                -result.bottleneck_energy_j,

                result.total_distance_m
            )

            candidates.append(
                (
                    score,
                    result
                )
            )

        if not candidates:
            return None

        # Only shortest-hop candidates
        # are allowed at this stage.
        min_hops = min(
            item[1].hop_count
            for item
            in candidates
        )

        candidates = [
            item
            for item
            in candidates
            if item[1].hop_count
            ==
            min_hops
        ]

        candidates.sort(
            key=lambda item:
                item[0]
        )

        return candidates[0][1]

    def route_source(
        self,
        source_id,
        load_factors=None,
        overloaded_nodes=None
    ) -> LBECMHRRouteResult | None:
        """
        Route a single source with load balancing and detour bounds.
        """
        load_factors = load_factors or {}
        overloaded_nodes = overloaded_nodes or set()

        sensor = self.sensor_map.get(source_id)
        if sensor is None or not sensor.is_alive():
            return None

        # Baseline: energy constraint only
        energy_graph = self._build_relay_graph(
            exclude_overloaded=False
        )
        _, energy_labels = self._build_labels(
            energy_graph,
            load_factors
        )

        baseline = self._route_source(
            source_id,
            energy_graph,
            energy_labels
        )
        if baseline is None:
            return None

        # Preferred: avoid overloaded relays
        preferred_graph = self._build_relay_graph(
            overloaded_nodes=overloaded_nodes,
            exclude_overloaded=True
        )
        _, preferred_labels = self._build_labels(
            preferred_graph,
            load_factors
        )

        preferred = self._route_source(
            source_id,
            preferred_graph,
            preferred_labels
        )

        if (
            preferred is not None
            and
            preferred.hop_count <= (baseline.hop_count + self.max_extra_hops)
        ):
            preferred.baseline_hop_count = baseline.hop_count
            preferred.detour_hops = (
                preferred.hop_count - baseline.hop_count
            )
            preferred.used_overload_fallback = False
            return preferred

        if self.allow_overload_fallback:
            baseline.baseline_hop_count = baseline.hop_count
            baseline.detour_hops = 0
            baseline.used_overload_fallback = True
            return baseline

        return None

    # ==================================================
    # Build all routes once per round
    # ==================================================

    def build_route_table(
        self,
        load_factors: dict,
        overloaded_nodes: set
    ) -> dict:

        # ----------------------------------
        # Baseline:
        # energy constraint only.
        # ----------------------------------

        energy_graph = (
            self._build_relay_graph(
                exclude_overloaded=False
            )
        )

        (
            _,
            energy_labels
        ) = self._build_labels(
            energy_graph,
            load_factors
        )

        # ----------------------------------
        # Preferred:
        # energy + no overloaded relays.
        # ----------------------------------

        preferred_graph = (
            self._build_relay_graph(
                overloaded_nodes=(
                    overloaded_nodes
                ),

                exclude_overloaded=True
            )
        )

        (
            _,
            preferred_labels
        ) = self._build_labels(
            preferred_graph,
            load_factors
        )

        route_table = {}

        for sensor in (
            self.network.sensors
        ):

            source_id = (
                sensor.node_id
            )

            if not sensor.is_alive():

                route_table[
                    source_id
                ] = None

                continue

            baseline = (
                self._route_source(
                    source_id,
                    energy_graph,
                    energy_labels
                )
            )

            if baseline is None:

                route_table[
                    source_id
                ] = None

                continue

            preferred = (
                self._route_source(
                    source_id,
                    preferred_graph,
                    preferred_labels
                )
            )

            # --------------------------------
            # Preferred route accepted only
            # within bounded detour.
            # --------------------------------

            if (
                preferred is not None
                and
                preferred.hop_count
                <=
                (
                    baseline.hop_count
                    +
                    self.max_extra_hops
                )
            ):

                preferred.baseline_hop_count = (
                    baseline.hop_count
                )

                preferred.detour_hops = (
                    preferred.hop_count
                    -
                    baseline.hop_count
                )

                preferred.used_overload_fallback = (
                    False
                )

                route_table[
                    source_id
                ] = preferred

                continue

            # --------------------------------
            # No balanced route available.
            # Keep connectivity by using
            # energy-valid route.
            # --------------------------------

            if self.allow_overload_fallback:

                baseline.baseline_hop_count = (
                    baseline.hop_count
                )

                baseline.detour_hops = 0

                baseline.used_overload_fallback = (
                    True
                )

                route_table[
                    source_id
                ] = baseline

            else:

                route_table[
                    source_id
                ] = None

        return route_table


def find_lb_ecmhr_route(
    network,
    source_id,
    energy_threshold_ratio: float = 0.20,
    load_factors: dict = None,
    overloaded_nodes: set = None,
    max_extra_hops: int = 1,
    allow_overload_fallback: bool = True
) -> LBECMHRRouteResult | None:
    """
    Convenience function for routing a single source with LB-ECMHR.
    """
    router = LBECMHRRouter(
        network=network,
        energy_threshold_ratio=energy_threshold_ratio,
        max_extra_hops=max_extra_hops,
        allow_overload_fallback=allow_overload_fallback
    )
    return router.route_source(
        source_id=source_id,
        load_factors=load_factors,
        overloaded_nodes=overloaded_nodes
    )
