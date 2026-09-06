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

        self.history = []
        self.fnd_round = None
        self.hnd_round = None
        self.lnd_round = None

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

            sensor_type=sensor.sensor_type,

            payload_size_bytes=(
                self.packet_size_bytes
            ),

            created_round=(
                self.current_round
            )
        )

        sensor.generated_packets += 1

        self.generated_packets += 1

        self.generated_bytes += (
            packet.payload_size_bytes
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

        consumed = sensor.consume_energy(
            amount_j=amount_j,

            energy_threshold_ratio=(
                self.energy_threshold_ratio
            )
        )

        self.total_energy_consumed_j += (
            consumed
        )

        return consumed

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

                if sender_id == source_id:
                    sender.sent_packets += 1

                else:
                    sender.forwarded_packets += 1

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

        # Sink successfully received packet

        packet.delivered = True

        packet.delay_ms = (
            packet.hop_count
            * self.per_hop_delay_ms
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

        self._record_history()

    def _update_lifetime_metrics(
        self
    ) -> None:

        dead_count = sum(
            1
            for sensor in self.network.sensors
            if not sensor.is_alive()
        )

        total = len(
            self.network.sensors
        )

        if (
            dead_count >= 1
            and self.fnd_round is None
        ):

            self.fnd_round = (
                self.current_round
            )

        if (
            dead_count >= ceil(total / 2)
            and self.hnd_round is None
        ):

            self.hnd_round = (
                self.current_round
            )

        if (
            dead_count >= total
            and self.lnd_round is None
        ):

            self.lnd_round = (
                self.current_round
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
                ]
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

        print("=" * 50)