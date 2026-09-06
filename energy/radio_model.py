from dataclasses import dataclass
import math


@dataclass(frozen=True)
class RadioEnergyModel:
    """
    First-order radio energy model.
    """

    e_elec_j_per_bit: float
    eps_fs_j_per_bit_m2: float
    eps_mp_j_per_bit_m4: float

    @classmethod
    def from_config(
        cls,
        config: dict
    ) -> "RadioEnergyModel":

        energy = config["energy"]

        return cls(
            e_elec_j_per_bit=(
                energy["e_elec_nj_per_bit"]
                * 1e-9
            ),

            eps_fs_j_per_bit_m2=(
                energy["eps_fs_pj_per_bit_m2"]
                * 1e-12
            ),

            eps_mp_j_per_bit_m4=(
                energy["eps_mp_pj_per_bit_m4"]
                * 1e-12
            )
        )

    @property
    def crossover_distance_m(self) -> float:
        """
        d0 = sqrt(eps_fs / eps_mp)
        """

        return math.sqrt(
            self.eps_fs_j_per_bit_m2
            /
            self.eps_mp_j_per_bit_m4
        )

    def tx_energy(
        self,
        packet_size_bytes: int,
        distance_m: float
    ) -> float:
        """
        Energy required to transmit a packet.
        """

        if packet_size_bytes < 0:
            raise ValueError(
                "Packet size cannot be negative."
            )

        if distance_m < 0:
            raise ValueError(
                "Distance cannot be negative."
            )

        bits = packet_size_bytes * 8

        electronics = (
            bits * self.e_elec_j_per_bit
        )

        if (
            distance_m
            < self.crossover_distance_m
        ):

            amplifier = (
                bits
                * self.eps_fs_j_per_bit_m2
                * distance_m ** 2
            )

        else:

            amplifier = (
                bits
                * self.eps_mp_j_per_bit_m4
                * distance_m ** 4
            )

        return electronics + amplifier

    def rx_energy(
        self,
        packet_size_bytes: int
    ) -> float:
        """
        Energy required to receive a packet.
        """

        if packet_size_bytes < 0:
            raise ValueError(
                "Packet size cannot be negative."
            )

        bits = packet_size_bytes * 8

        return (
            bits
            * self.e_elec_j_per_bit
        )