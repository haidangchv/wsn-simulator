from dataclasses import dataclass
from math import ceil

import networkx as nx

from core.network import WirelessSensorNetwork
from core.packet import Packet
from energy.radio_model import (
    RadioEnergyModel
)
from routing.minimum_hop import (
    find_minimum_hop_route
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
        config: dict
    ):

        self.network = network
        self.config = config

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

        graph = self._active_graph()

        route = find_minimum_hop_route(
            graph=graph,
            source_id=source_id,
            sink_id=self.network.sink.node_id
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
                graph[
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

    def get_metrics(self) -> dict:

        alive = sum(
            sensor.is_alive()
            for sensor in self.network.sensors
        )

        dead = (
            len(self.network.sensors)
            - alive
        )

        if self.generated_packets > 0:

            pdr = (
                self.delivered_packets
                /
                self.generated_packets
            )

        else:
            pdr = 0.0

        return {
            "round":
                self.current_round,

            "alive_nodes":
                alive,

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

            "total_energy_consumed_j":
                self.total_energy_consumed_j,

            "fnd_round":
                self.fnd_round,

            "hnd_round":
                self.hnd_round,

            "lnd_round":
                self.lnd_round
        }