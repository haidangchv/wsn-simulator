from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SensorMeasurement:
    source_id: int

    sensor_type: str

    round_number: int

    simulation_time_seconds: float

    value: float

    unit: str

    timestamp: datetime | None = None