from dataclasses import dataclass, field
from typing import List


@dataclass
class SensorNode:
    node_id: int
    x: float
    y: float
    sensor_type: str

    initial_energy: float
    remaining_energy: float

    transmission_range: float

    state: str = "ALIVE"
    relay_enabled: bool = True

    neighbors: List[int] = field(default_factory=list)

    generated_packets: int = 0
    sent_packets: int = 0
    received_packets: int = 0
    forwarded_packets: int = 0

    def energy_ratio(self) -> float:
        if self.initial_energy <= 0:
            return 0.0

        return self.remaining_energy / self.initial_energy

    def is_alive(self) -> bool:
        return self.remaining_energy > 0

    def update_state(self, energy_threshold_ratio: float) -> None:
        """
        Update sensor state based on remaining energy.
        """

        if self.remaining_energy <= 0:
            self.remaining_energy = 0
            self.state = "DEAD"
            self.relay_enabled = False

        elif self.energy_ratio() <= energy_threshold_ratio:
            self.state = "LOW_ENERGY"
            self.relay_enabled = False

        else:
            self.state = "ALIVE"
            self.relay_enabled = True

    def __repr__(self) -> str:
        return (
            f"SensorNode("
            f"id={self.node_id}, "
            f"type={self.sensor_type}, "
            f"position=({self.x:.2f}, {self.y:.2f}), "
            f"energy={self.remaining_energy:.2f}J, "
            f"state={self.state}"
            f")"
        )