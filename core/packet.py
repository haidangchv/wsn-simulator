from dataclasses import dataclass, field
from typing import Union


NodeId = Union[int, str]


@dataclass
class Packet:
    source_id: int

    sequence_number: int

    sensor_type: str

    payload_size_bytes: int

    created_round: int

    measurement_value: float | None = None

    measurement_unit: str | None = None

    simulation_time_seconds: float = 0.0

    raw_payload_size_bytes: int | None = None

    encoded_payload_size_bytes: int | None = None

    compressed_payload_size_bytes: int | None = None

    delivered: bool = False

    dropped_reason: str | None = None

    hop_count: int = 0

    delay_ms: float = 0.0

    route: list[NodeId] = field(
        default_factory=list
    )