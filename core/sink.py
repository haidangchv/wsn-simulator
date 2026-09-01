from dataclasses import dataclass


@dataclass
class SinkNode:
    x: float
    y: float

    node_id: str = "SINK"

    received_packets: int = 0
    received_bytes: int = 0

    def __repr__(self) -> str:
        return (
            f"SinkNode("
            f"id={self.node_id}, "
            f"position=({self.x:.2f}, {self.y:.2f})"
            f")"
        )