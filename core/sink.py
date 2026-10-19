import math
from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class SinkNode:
    x: float
    y: float

    node_id: str = "SINK"

    received_packets: int = 0
    received_bytes: int = 0

    # Mobility attributes
    current_waypoint: int | str = 0
    initial_x: float = 0.0
    initial_y: float = 0.0
    last_move_round: int = 0
    movement_count: int = 0
    total_move_distance_m: float = 0.0
    movement_history: List[dict] = field(
        default_factory=list
    )

    def __post_init__(self):
        if self.initial_x == 0.0 and self.initial_y == 0.0:
            self.initial_x = self.x
            self.initial_y = self.y

    def move_to(
        self,
        new_x: float,
        new_y: float,
        waypoint_id: int | str = 0,
        round_num: int = 0,
        reason: str = ""
    ) -> float:
        """
        Di chuyển Sink sang tọa độ mới và ghi nhận lịch sử di chuyển.
        """
        distance = math.hypot(
            new_x - self.x,
            new_y - self.y
        )

        record = {
            "round": round_num,
            "from_pos": (self.x, self.y),
            "to_pos": (new_x, new_y),
            "waypoint": waypoint_id,
            "distance_m": distance,
            "reason": reason
        }
        self.movement_history.append(record)

        self.x = new_x
        self.y = new_y
        self.current_waypoint = waypoint_id
        self.last_move_round = round_num
        self.movement_count += 1
        self.total_move_distance_m += distance

        return distance

    def __repr__(self) -> str:
        return (
            f"SinkNode("
            f"id={self.node_id}, "
            f"position=({self.x:.2f}, {self.y:.2f}), "
            f"waypoint={self.current_waypoint}, "
            f"moves={self.movement_count})"
        )