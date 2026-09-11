from dataclasses import dataclass
from math import ceil
from routing.ecmhr import (
    find_ecmhr_route
)
import networkx as nx

from core.network import WirelessSensorNetwork
from core.packet import Packet
from energy.radio_model import (
    RadioEnergyModel
)
from routing.minimum_hop import (
    find_minimum_hop_route
)
from routing.route_manager import (
    RouteManager
)
from data.generator import (
    EnvironmentalDataGenerator
)
from environment.collector import (
    EnvironmentalDataCollector
)
from environment.analyzer import (
    EnvironmentalAnalyzer
)
from environment.degradation import (
    ZoneHistoryTracker
)



@dataclass
class TransmissionResult:
    packet: Packet

    delivered: bool

    energy_consumed_j: float

    failed_node: int | str | None = None


class WSNSimulator:

    def __init__(
        self,
        network: WirelessSensorNetwork,
        config: dict,
        routing_algorithm: str | None = None
    ):

        self.network = network
        self.config = config

        routing_config = (
            config.get(
                "routing",
                {}
            )
        )

        self.routing_algorithm = (
            routing_algorithm
            or routing_config.get(
                "algorithm",
                "minimum_hop"
            )
        )

        self.allow_emergency_mode = (
            routing_config.get(
                "allow_emergency_mode",
                False
            )
        )

        self.emergency_threshold_ratio = (
            routing_config.get(
                "emergency_threshold_ratio",
                0.10
            )
        )

        self.route_manager = RouteManager(
            network=self.network,
            config=self.config,
            algorithm=self.routing_algorithm
        )

        self.set_routing_algorithm(
            self.routing_algorithm
        )

        self.radio = (
            RadioEnergyModel.from_config(
                config
            )
        )

        self.energy_threshold_ratio = (
            config["sensor"][
                "energy_threshold_ratio"
            ]
        )

        self.packet_size_bytes = (
            config["packet"][
                "payload_size_bytes"
            ]
        )

        self.per_hop_delay_ms = (
            config["energy"][
                "per_hop_delay_ms"
            ]
        )

        self.current_round = 0

        self.sequence_numbers = {
            sensor.node_id: 0
            for sensor in network.sensors
        }

        self.generated_packets = 0
        self.delivered_packets = 0
        self.dropped_packets = 0

        self.generated_bytes = 0
        self.delivered_bytes = 0

        self.total_energy_consumed_j = 0.0
        self.total_delay_ms = 0.0
        self.total_delivered_hops = 0

        self.sampling_interval_seconds = (
            config["packet"][
                "sampling_interval_seconds"
            ]
        )

        environment_config = (
            config.get(
                "environment",
                {}
            )
        )

        self.environment_enabled = (
            environment_config.get(
                "enabled",
                False
            )
        )

        if self.environment_enabled:

            self.environment_generator = (
                EnvironmentalDataGenerator(
                    config
                )
            )

            self.environment_collector = (
                EnvironmentalDataCollector()
            )

            self.environment_analyzer = (
                EnvironmentalAnalyzer(
                    config
                )
            )

            self.zone_history_tracker = (
                ZoneHistoryTracker()
            )

            self.environment_analysis_interval = int(
                config[
                    "environment"
                ].get(
                    "analysis_interval_rounds",
                    10
                )
            )

        else:

            self.environment_generator = None

            self.environment_collector = None

            self.environment_analyzer = None

            self.zone_history_tracker = None

            self.environment_analysis_interval = 10

        self.history = []
        self.fnd_round = None
        self.hnd_round = None
        self.lnd_round = None

        radio_config = config.get(
            "radio",
            {}
        )

        self.data_rate_bps = float(
            radio_config.get(
                "data_rate_bps",
                250000
            )
        )

        self.processing_delay_ms_per_hop = float(
            radio_config.get(
                "processing_delay_ms_per_hop",
                1.0
            )
        )

        self.propagation_speed_m_s = float(
            radio_config.get(
                "propagation_speed_m_s",
                300000000
            )
        )

        self.total_transmission_time_ms = 0.0
        self.total_processing_delay_ms = 0.0
        self.total_propagation_delay_ms = 0.0

        # Actual traffic over wireless links.
        # A 128-byte packet over 5 hops contributes
        # 5 * 128 bytes here.
        self.total_link_tx_bytes = 0
        self.total_link_rx_bytes = 0

        self.lifetime_snapshots = {
            "FND": None,
            "HND": None,
            "LND": None
        }

        self.first_disconnection_round = None
        self.connectivity_90_round = None
        self.connectivity_50_round = None
        self.zero_connectivity_round = None

        self.sensor_map = {
            sensor.node_id: sensor
            for sensor in network.sensors
        }


    def _active_graph(self) -> nx.Graph:
        """
        Minimum-Hop baseline excludes only DEAD nodes.

        LOW_ENERGY nodes may still be relays.
        """

        graph = self.network.graph.copy()

        dead_nodes = [
            sensor.node_id
            for sensor in self.network.sensors
            if not sensor.is_alive()
        ]

        graph.remove_nodes_from(
            dead_nodes
        )

        return graph

    def set_routing_algorithm(
        self,
        algorithm: str
    ) -> None:

        supported = {
            "minimum_hop",
            "ecmhr"
        }

        if algorithm not in supported:

            raise ValueError(
                f"Unsupported routing algorithm: "
                f"{algorithm}"
            )

        self.routing_algorithm = (
            algorithm
        )

        if hasattr(self, "route_manager"):
            self.route_manager.set_algorithm(
                algorithm
            )


    def find_current_route(
        self,
        source_id: int
    ):

        if source_id not in self.sensor_map:
            return None

        source = self.sensor_map[
            source_id
        ]

        if not source.is_alive():
            return None

        if (
            self.routing_algorithm
            == "minimum_hop"
        ):

            graph = self._active_graph()

            return find_minimum_hop_route(
                graph=graph,
                source_id=source_id,
                sink_id=(
                    self.network.sink.node_id
                )
            )

        if (
            self.routing_algorithm
            == "ecmhr"
        ):

            return find_ecmhr_route(
                graph=self.network.graph,

                sensor_map=self.sensor_map,

                source_id=source_id,

                sink_id=(
                    self.network.sink.node_id
                ),

                energy_threshold_ratio=(
                    self.energy_threshold_ratio
                ),

                allow_emergency_mode=(
                    self.allow_emergency_mode
                ),

                emergency_threshold_ratio=(
                    self.emergency_threshold_ratio
                )
            )

        return None

    def _create_packet(
        self,
        source_id: int
    ) -> Packet:

        sensor = self.sensor_map[source_id]

        measurement = None

        if (
            self.environment_enabled
            and
            sensor.is_alive()
        ):

            simulation_time_seconds = (
                self.current_round
                *
                self.sampling_interval_seconds
            )

            measurement = (
                self.environment_generator.generate(
                    sensor=sensor,

                    round_number=(
                        self.current_round
                    ),

                    simulation_time_seconds=(
                        simulation_time_seconds
                    )
                )
            )

        self.sequence_numbers[
            source_id
        ] += 1

        packet = Packet(
            source_id=source_id,

            sequence_number=(
                self.sequence_numbers[
                    source_id
                ]
            ),

            sensor_type=(
                sensor.sensor_type
            ),

            payload_size_bytes=(
                self.packet_size_bytes
            ),

            created_round=(
                self.current_round
            ),

            measurement_value=(
                measurement.value
                if measurement
                else None
            ),

            measurement_unit=(
                measurement.unit
                if measurement
                else None
            ),

            simulation_time_seconds=(
                measurement.simulation_time_seconds
                if measurement
                else 0.0
            ),

            raw_payload_size_bytes=(
                self.packet_size_bytes
            )
        )

        sensor.generated_packets += 1

        self.generated_packets += 1

        self.generated_bytes += (
            packet.payload_size_bytes
        )

        if (
            self.environment_collector
            is not None
        ):

            self.environment_collector.record_generated(
                packet=packet,
                sensor=sensor
            )

        return packet

    def _consume_sensor_energy(
        self,
        sensor_id: int,
        amount_j: float
    ) -> float:

        sensor = self.sensor_map[
            sensor_id
        ]

        was_alive = (
            sensor.is_alive()
        )

        actual_consumed = (
            sensor.consume_energy(
                amount_j=amount_j,

                energy_threshold_ratio=(
                    self.energy_threshold_ratio
                )
            )
        )

        self.total_energy_consumed_j += (
            actual_consumed
        )

        if (
            was_alive
            and
            not sensor.is_alive()
            and
            sensor.death_round is None
        ):

            sensor.death_round = (
                self.current_round
            )

        return actual_consumed

    def _link_delay_components(
        self,
        packet_size_bytes: int,
        distance_m: float
    ) -> tuple[float, float, float]:

        packet_bits = (
            packet_size_bytes
            * 8
        )

        transmission_ms = (
            packet_bits
            /
            self.data_rate_bps
            *
            1000
        )

        propagation_ms = (
            distance_m
            /
            self.propagation_speed_m_s
            *
            1000
        )

        processing_ms = (
            self.processing_delay_ms_per_hop
        )

        return (
            transmission_ms,
            propagation_ms,
            processing_ms
        )


    def transmit_from_sensor(
        self,
        source_id: int
    ) -> TransmissionResult:

        source = self.sensor_map[
            source_id
        ]

        packet = self._create_packet(
            source_id
        )

        if not source.is_alive():

            packet.dropped_reason = (
                "SOURCE_DEAD"
            )

            self.dropped_packets += 1

            return TransmissionResult(
                packet=packet,
                delivered=False,
                energy_consumed_j=0.0,
                failed_node=source_id
            )

        route = self.route_manager.get_route(
            source_id
        )

        if route is None:

            packet.dropped_reason = (
                "NO_ROUTE"
            )

            self.dropped_packets += 1

            return TransmissionResult(
                packet=packet,
                delivered=False,
                energy_consumed_j=0.0
            )

        packet.route = route.path
        packet.hop_count = route.hop_count

        transmission_energy = 0.0

        for index in range(
            len(route.path) - 1
        ):

            sender_id = route.path[index]

            receiver_id = (
                route.path[index + 1]
            )

            distance = (
                self.network.graph[
                    sender_id
                ][
                    receiver_id
                ]["distance"]
            )

            (
                transmission_ms,
                propagation_ms,
                processing_ms
            ) = self._link_delay_components(
                packet_size_bytes=(
                    packet.payload_size_bytes
                ),

                distance_m=distance
            )

            packet.transmission_time_ms += (
                transmission_ms
            )

            packet.propagation_delay_ms += (
                propagation_ms
            )

            packet.processing_delay_ms += (
                processing_ms
            )

            # ------------------------
            # TRANSMISSION ENERGY
            # ------------------------

            if (
                sender_id
                != self.network.sink.node_id
            ):

                sender = self.sensor_map[
                    sender_id
                ]

                tx_required = (
                    self.radio.tx_energy(
                        packet_size_bytes=(
                            packet.payload_size_bytes
                        ),
                        distance_m=distance
                    )
                )

                if (
                    sender.remaining_energy
                    < tx_required
                ):

                    consumed = (
                        self._consume_sensor_energy(
                            sender_id,
                            sender.remaining_energy
                        )
                    )

                    transmission_energy += (
                        consumed
                    )

                    packet.dropped_reason = (
                        "TX_ENERGY_INSUFFICIENT"
                    )

                    self.dropped_packets += 1

                    return TransmissionResult(
                        packet=packet,
                        delivered=False,
                        energy_consumed_j=(
                            transmission_energy
                        ),
                        failed_node=sender_id
                    )

                consumed = (
                    self._consume_sensor_energy(
                        sender_id,
                        tx_required
                    )
                )

                transmission_energy += (
                    consumed
                )

                self.total_link_tx_bytes += (
                    packet.payload_size_bytes
                )

                sender.transmitted_bytes += (
                    packet.payload_size_bytes
                )

                if sender_id == source_id:
                    sender.sent_packets += 1

                else:
                    sender.forwarded_packets += 1

                    sender.forwarded_bytes += (
                        packet.payload_size_bytes
                    )

            # ------------------------
            # RECEPTION ENERGY
            # ------------------------

            if (
                receiver_id
                != self.network.sink.node_id
            ):

                receiver = self.sensor_map[
                    receiver_id
                ]

                rx_required = (
                    self.radio.rx_energy(
                        packet.payload_size_bytes
                    )
                )

                if (
                    receiver.remaining_energy
                    < rx_required
                ):

                    consumed = (
                        self._consume_sensor_energy(
                            receiver_id,
                            receiver.remaining_energy
                        )
                    )

                    transmission_energy += (
                        consumed
                    )

                    packet.dropped_reason = (
                        "RX_ENERGY_INSUFFICIENT"
                    )

                    self.dropped_packets += 1

                    return TransmissionResult(
                        packet=packet,
                        delivered=False,
                        energy_consumed_j=(
                            transmission_energy
                        ),
                        failed_node=receiver_id
                    )

                consumed = (
                    self._consume_sensor_energy(
                        receiver_id,
                        rx_required
                    )
                )

                transmission_energy += (
                    consumed
                )

                receiver.received_packets += 1

                receiver.received_bytes += (
                    packet.payload_size_bytes
                )

                self.total_link_rx_bytes += (
                    packet.payload_size_bytes
                )

            else:

                self.total_link_rx_bytes += (
                    packet.payload_size_bytes
                )

        # Sink successfully received packet

        packet.delivered = True

        packet.delay_ms = (
            packet.transmission_time_ms
            +
            packet.propagation_delay_ms
            +
            packet.processing_delay_ms
        )

        self.total_transmission_time_ms += (
            packet.transmission_time_ms
        )

        self.total_propagation_delay_ms += (
            packet.propagation_delay_ms
        )

        self.total_processing_delay_ms += (
            packet.processing_delay_ms
        )

        self.total_delay_ms += (
            packet.delay_ms
        )


        self.total_delivered_hops += (
            packet.hop_count
        )

        self.delivered_packets += 1

        self.delivered_bytes += (
            packet.payload_size_bytes
        )

        self.network.sink.received_packets += 1

        self.network.sink.received_bytes += (
            packet.payload_size_bytes
        )

        if (
            self.environment_collector
            is not None
        ):

            source_sensor = (
                self.sensor_map[
                    packet.source_id
                ]
            )

            self.environment_collector.record_received(
                packet=packet,
                sensor=source_sensor
            )

        return TransmissionResult(
            packet=packet,
            delivered=True,
            energy_consumed_j=(
                transmission_energy
            )
        )

    def run_round(self) -> None:

        self.current_round += 1

        self.route_manager.prepare_round()

        # Snapshot of nodes alive at beginning
        # of the round.
        source_ids = [
            sensor.node_id
            for sensor in self.network.sensors
            if sensor.is_alive()
        ]

        for source_id in source_ids:

            # Sensor may have died earlier in
            # this round while acting as relay.
            if not self.sensor_map[
                source_id
            ].is_alive():

                continue

            self.transmit_from_sensor(
                source_id
            )

        self._update_lifetime_metrics()

        self._update_connectivity_lifetime_metrics()

        self._record_environment_snapshot()

        self._record_history()

    def _record_environment_snapshot(
        self
    ) -> None:

        if not self.environment_enabled:
            return

        if (
            self.environment_collector
            is None
        ):
            return

        if (
            not self.environment_collector
            .received_records
        ):
            return

        should_record = (
            self.current_round == 1
            or
            self.current_round
            %
            self.environment_analysis_interval
            ==
            0
        )

        if not should_record:
            return

        zone_snapshot = (
            self.environment_analyzer
            .build_zone_snapshot(
                collector=(
                    self.environment_collector
                ),

                current_round=(
                    self.current_round
                )
            )
        )

        self.zone_history_tracker.record_snapshot(
            zone_dataframe=(
                zone_snapshot
            ),

            round_number=(
                self.current_round
            )
        )

    def _create_lifetime_snapshot(
        self
    ) -> dict:

        return {
            "round":
                self.current_round,

            "generated_packets":
                self.generated_packets,

            "delivered_packets":
                self.delivered_packets,

            "dropped_packets":
                self.dropped_packets,

            "delivered_bytes":
                self.delivered_bytes,

            "network_tx_bytes":
                self.total_link_tx_bytes,

            "total_energy_consumed_j":
                self.total_energy_consumed_j
        }

    def _update_lifetime_metrics(
        self
    ) -> None:

        total_nodes = len(
            self.network.sensors
        )

        dead_count = sum(
            1
            for sensor
            in self.network.sensors
            if not sensor.is_alive()
        )

        # First Node Death
        if (
            dead_count >= 1
            and
            self.fnd_round is None
        ):

            self.fnd_round = (
                self.current_round
            )

            self.lifetime_snapshots[
                "FND"
            ] = (
                self._create_lifetime_snapshot()
            )

        # Half Nodes Dead
        half_nodes = (
            total_nodes + 1
        ) // 2

        if (
            dead_count >= half_nodes
            and
            self.hnd_round is None
        ):

            self.hnd_round = (
                self.current_round
            )

            self.lifetime_snapshots[
                "HND"
            ] = (
                self._create_lifetime_snapshot()
            )

        # Last Node Death
        if (
            dead_count >= total_nodes
            and
            self.lnd_round is None
        ):

            self.lnd_round = (
                self.current_round
            )

            self.lifetime_snapshots[
                "LND"
            ] = (
                self._create_lifetime_snapshot()
            )

    def _minimum_hop_connected_ids(
        self
    ) -> set[int]:

        graph = (
            self.network.graph.copy()
        )

        dead_nodes = [
            sensor.node_id
            for sensor
            in self.network.sensors
            if not sensor.is_alive()
        ]

        graph.remove_nodes_from(
            dead_nodes
        )

        sink_id = (
            self.network.sink.node_id
        )

        if sink_id not in graph:
            return set()

        component = (
            nx.node_connected_component(
                graph,
                sink_id
            )
        )

        return {
            node_id
            for node_id in component
            if node_id != sink_id
        }

    def _ecmhr_connected_ids_for_threshold(
        self,
        threshold_ratio: float
    ) -> set[int]:

        sink_id = (
            self.network.sink.node_id
        )

        alive_sensors = [
            sensor
            for sensor
            in self.network.sensors
            if sensor.is_alive()
        ]

        eligible_relays = {
            sensor.node_id
            for sensor
            in alive_sensors
            if (
                sensor.energy_ratio()
                >
                threshold_ratio
            )
        }

        relay_graph = (
            self.network.graph.subgraph(
                eligible_relays
                |
                {sink_id}
            )
            .copy()
        )

        if sink_id not in relay_graph:
            return set()

        sink_component = (
            nx.node_connected_component(
                relay_graph,
                sink_id
            )
        )

        connected = set()

        for sensor in alive_sensors:

            source_id = (
                sensor.node_id
            )

            # Normal eligible source.
            if source_id in sink_component:

                connected.add(
                    source_id
                )

                continue

            # LOW_ENERGY source may still send its
            # own data through a valid relay.
            for neighbor in (
                self.network.graph.neighbors(
                    source_id
                )
            ):

                if (
                    neighbor == sink_id
                    or
                    neighbor
                    in sink_component
                ):

                    connected.add(
                        source_id
                    )

                    break

        return connected

    def get_connected_alive_sensor_ids(
        self
    ) -> set[int]:

        if (
            self.routing_algorithm
            ==
            "minimum_hop"
        ):

            return (
                self._minimum_hop_connected_ids()
            )

        normal_connected = (
            self._ecmhr_connected_ids_for_threshold(
                self.energy_threshold_ratio
            )
        )

        if not self.allow_emergency_mode:

            return normal_connected

        emergency_connected = (
            self._ecmhr_connected_ids_for_threshold(
                self.emergency_threshold_ratio
            )
        )

        return (
            normal_connected
            |
            emergency_connected
        )

    def get_connectivity_metrics(
        self
    ) -> dict:

        alive_ids = {
            sensor.node_id
            for sensor
            in self.network.sensors
            if sensor.is_alive()
        }

        connected_ids = (
            self.get_connected_alive_sensor_ids()
        )

        alive_count = len(
            alive_ids
        )

        connected_count = len(
            connected_ids
        )

        disconnected_count = (
            alive_count
            -
            connected_count
        )

        if alive_count > 0:

            ratio = (
                connected_count
                /
                alive_count
            )

        else:

            ratio = 0.0

        return {
            "connected_alive_nodes":
                connected_count,

            "disconnected_alive_nodes":
                disconnected_count,

            "connectivity_ratio":
                ratio
        }

    def _update_connectivity_lifetime_metrics(
        self
    ) -> None:

        metrics = (
            self.get_connectivity_metrics()
        )

        alive = (
            metrics[
                "connected_alive_nodes"
            ]
            +
            metrics[
                "disconnected_alive_nodes"
            ]
        )

        connected = (
            metrics[
                "connected_alive_nodes"
            ]
        )

        ratio = (
            metrics[
                "connectivity_ratio"
            ]
        )

        if (
            alive > 0
            and
            ratio < 1.0
            and
            self.first_disconnection_round
            is None
        ):

            self.first_disconnection_round = (
                self.current_round
            )

        if (
            alive > 0
            and
            ratio < 0.90
            and
            self.connectivity_90_round
            is None
        ):

            self.connectivity_90_round = (
                self.current_round
            )

        if (
            alive > 0
            and
            ratio < 0.50
            and
            self.connectivity_50_round
            is None
        ):

            self.connectivity_50_round = (
                self.current_round
            )

        if (
            alive > 0
            and
            connected == 0
            and
            self.zero_connectivity_round
            is None
        ):

            self.zero_connectivity_round = (
                self.current_round
            )

    def _snapshot_value(
        self,
        milestone: str,
        key: str,
        default=None
    ):

        snapshot = (
            self.lifetime_snapshots.get(
                milestone
            )
        )

        if snapshot is None:
            return default

        return snapshot.get(
            key,
            default
        )


    def run(
        self,
        rounds: int
    ) -> None:

        for _ in range(rounds):

            if self.lnd_round is not None:
                break

            self.run_round()

    def _record_history(self) -> None:
        """
        Store a snapshot of cumulative metrics
        after the current round.
        """

        snapshot = self.get_metrics().copy()

        self.history.append(
            snapshot
        )

    def get_metrics(self) -> dict:

        total_nodes = len(
            self.network.sensors
        )

        alive = sum(
            1
            for sensor in self.network.sensors
            if sensor.is_alive()
        )

        dead = total_nodes - alive

        low_energy = sum(
            1
            for sensor in self.network.sensors
            if sensor.state == "LOW_ENERGY"
        )

        total_remaining_energy = sum(
            sensor.remaining_energy
            for sensor in self.network.sensors
        )

        average_remaining_energy = (
            total_remaining_energy / total_nodes
            if total_nodes > 0
            else 0.0
        )

        elapsed_seconds = (
            self.current_round
            * self.sampling_interval_seconds
        )

        # Packet Delivery Ratio

        if self.generated_packets > 0:

            pdr = (
                self.delivered_packets
                / self.generated_packets
            )

        else:
            pdr = 0.0

        # Throughput at Sink

        if elapsed_seconds > 0:

            throughput_bps = (
                self.delivered_bytes
                * 8
                / elapsed_seconds
            )

        else:
            throughput_bps = 0.0

        # Average End-to-End Delay

        if self.delivered_packets > 0:

            average_delay_ms = (
                self.total_delay_ms
                / self.delivered_packets
            )

            average_hop_count = (
                self.total_delivered_hops
                / self.delivered_packets
            )

        else:

            average_delay_ms = 0.0
            average_hop_count = 0.0

        # Useful bits delivered / Joule consumed

        if self.total_energy_consumed_j > 0:

            energy_efficiency_bits_per_j = (
                self.delivered_bytes
                * 8
                / self.total_energy_consumed_j
            )

        else:

            energy_efficiency_bits_per_j = 0.0

        routing_metrics = (
            self.route_manager.get_metrics()
        )

        connectivity = (
            self.get_connectivity_metrics()
        )

        if self.delivered_packets > 0:

            average_transmission_time_ms = (
                self.total_transmission_time_ms
                /
                self.delivered_packets
            )

        else:

            average_transmission_time_ms = 0.0

        link_data_rate_kbps = (
            self.data_rate_bps
            /
            1000
        )

        network_load_mb = (
            self.total_link_tx_bytes
            /
            (
                1024 ** 2
            )
        )

        delivered_data_mb = (
            self.delivered_bytes
            /
            (
                1024 ** 2
            )
        )

        return {
            "round":
                self.current_round,

            "elapsed_seconds":
                elapsed_seconds,

            "alive_nodes":
                alive,

            "low_energy_nodes":
                low_energy,

            "dead_nodes":
                dead,

            "generated_packets":
                self.generated_packets,

            "delivered_packets":
                self.delivered_packets,

            "dropped_packets":
                self.dropped_packets,

            "generated_bytes":
                self.generated_bytes,

            "delivered_bytes":
                self.delivered_bytes,

            "pdr":
                pdr,

            "throughput_bps":
                throughput_bps,

            "average_delay_ms":
                average_delay_ms,

            "average_hop_count":
                average_hop_count,

            "total_energy_consumed_j":
                self.total_energy_consumed_j,

            "total_remaining_energy_j":
                total_remaining_energy,

            "average_remaining_energy_j":
                average_remaining_energy,

            "energy_efficiency_bits_per_j":
                energy_efficiency_bits_per_j,

            "fnd_round":
                self.fnd_round,

            "hnd_round":
                self.hnd_round,

            "lnd_round":
                self.lnd_round,

            "routing_algorithm":
                self.routing_algorithm,

            "routing_requests":
                routing_metrics[
                    "routing_requests"
                ],

            "route_table_hits":
                routing_metrics[
                    "route_table_hits"
                ],

            "route_table_builds":
                routing_metrics[
                    "route_table_builds"
                ],

            "routing_reroutes":
                routing_metrics[
                    "routing_reroutes"
                ],

            "route_cache_hit_ratio":
                routing_metrics[
                    "route_cache_hit_ratio"
                ],

            "link_data_rate_bps":
                self.data_rate_bps,

            "average_transmission_time_ms":
                average_transmission_time_ms,

            "delivered_data_mb":
                delivered_data_mb,

            "network_load_mb":
                network_load_mb,

            "network_tx_bytes":
                self.total_link_tx_bytes,

            "network_rx_bytes":
                self.total_link_rx_bytes,

            "connected_alive_nodes":
                connectivity[
                    "connected_alive_nodes"
                ],

            "disconnected_alive_nodes":
                connectivity[
                    "disconnected_alive_nodes"
                ],

            "routing_connectivity_ratio":
                connectivity[
                    "connectivity_ratio"
                ],

            "first_disconnection_round":
                self.first_disconnection_round,

            "connectivity_90_round":
                self.connectivity_90_round,

            "connectivity_50_round":
                self.connectivity_50_round,

            "zero_connectivity_round":
                self.zero_connectivity_round,

            "delivered_bytes_at_fnd":
                self._snapshot_value(
                    "FND",
                    "delivered_bytes"
                ),

            "delivered_bytes_at_hnd":
                self._snapshot_value(
                    "HND",
                    "delivered_bytes"
                ),

            "delivered_bytes_at_lnd":
                self._snapshot_value(
                    "LND",
                    "delivered_bytes"
                ),

            "delivered_packets_at_fnd":
                self._snapshot_value(
                    "FND",
                    "delivered_packets"
                ),

            "delivered_packets_at_hnd":
                self._snapshot_value(
                    "HND",
                    "delivered_packets"
                ),

            "delivered_packets_at_lnd":
                self._snapshot_value(
                    "LND",
                    "delivered_packets"
                )
        }

    def print_summary(self) -> None:

        metrics = self.get_metrics()

        print()
        print("=" * 50)
        print("WSN SIMULATION SUMMARY")
        print("=" * 50)

        print(
            f"Round: "
            f"{metrics['round']}"
        )

        print(
            f"Simulation time: "
            f"{metrics['elapsed_seconds']:.0f} s"
        )

        print()

        print(
            f"Alive nodes: "
            f"{metrics['alive_nodes']}"
        )

        print(
            f"Low-energy nodes: "
            f"{metrics['low_energy_nodes']}"
        )

        print(
            f"Dead nodes: "
            f"{metrics['dead_nodes']}"
        )

        print()

        print(
            f"Generated packets: "
            f"{metrics['generated_packets']}"
        )

        print(
            f"Delivered packets: "
            f"{metrics['delivered_packets']}"
        )

        print(
            f"Dropped packets: "
            f"{metrics['dropped_packets']}"
        )

        print(
            f"PDR: "
            f"{metrics['pdr'] * 100:.2f}%"
        )

        print()

        print(
            f"Throughput: "
            f"{metrics['throughput_bps'] / 1000:.2f} kbps"
        )

        print(
            f"Average delay: "
            f"{metrics['average_delay_ms']:.2f} ms"
        )

        print(
            f"Average hop count: "
            f"{metrics['average_hop_count']:.2f}"
        )

        print()

        print(
            f"Energy consumed: "
            f"{metrics['total_energy_consumed_j']:.4f} J"
        )

        print(
            f"Energy remaining: "
            f"{metrics['total_remaining_energy_j']:.4f} J"
        )

        print(
            f"Energy efficiency: "
            f"{metrics['energy_efficiency_bits_per_j']:.2f} bit/J"
        )

        print()

        print(
            f"FND: "
            f"{metrics['fnd_round']}"
        )

        print(
            f"HND: "
            f"{metrics['hnd_round']}"
        )

        print(
            f"LND: "
            f"{metrics['lnd_round']}"
        )

        print()
        print("DATA TRANSFER")
        print("-" * 50)

        print(
            f"PHY data rate: "
            f"{metrics['link_data_rate_bps'] / 1000:.2f} kbps"
        )

        print(
            f"Actual throughput: "
            f"{metrics['throughput_bps'] / 1000:.2f} kbps"
        )

        print(
            f"Average TX time: "
            f"{metrics['average_transmission_time_ms']:.3f} ms"
        )

        print(
            f"Average E2E delay: "
            f"{metrics['average_delay_ms']:.3f} ms"
        )

        print(
            f"Delivered data: "
            f"{metrics['delivered_data_mb']:.3f} MB"
        )

        print(
            f"Total network TX load: "
            f"{metrics['network_load_mb']:.3f} MB"
        )

        print()
        print("CONNECTIVITY")
        print("-" * 50)

        print(
            f"Connected alive nodes: "
            f"{metrics['connected_alive_nodes']}"
        )

        print(
            f"Disconnected alive nodes: "
            f"{metrics['disconnected_alive_nodes']}"
        )

        print(
            f"Connectivity: "
            f"{metrics['routing_connectivity_ratio'] * 100:.2f}%"
        )

        print(
            f"First disconnection: "
            f"{metrics['first_disconnection_round']}"
        )

        print(
            f"90% connectivity round: "
            f"{metrics['connectivity_90_round']}"
        )

        print(
            f"50% connectivity round: "
            f"{metrics['connectivity_50_round']}"
        )

        print()
        print("DATA UNTIL NETWORK LIFETIME MILESTONES")
        print("-" * 50)

        for milestone in [
            "FND",
            "HND",
            "LND"
        ]:

            snapshot = (
                self.lifetime_snapshots[
                    milestone
                ]
            )

            if snapshot is None:

                print(
                    f"{milestone}: Not reached"
                )

                continue

            delivered_mb = (
                snapshot[
                    "delivered_bytes"
                ]
                /
                (
                    1024 ** 2
                )
            )

            network_mb = (
                snapshot[
                    "network_tx_bytes"
                ]
                /
                (
                    1024 ** 2
                )
            )

            print(
                f"{milestone}: "
                f"Round {snapshot['round']} | "
                f"Delivered {delivered_mb:.2f} MB | "
                f"Network TX {network_mb:.2f} MB"
            )

        print("=" * 50)