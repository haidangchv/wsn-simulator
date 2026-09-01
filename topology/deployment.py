from typing import List

import numpy as np

from core.sensor import SensorNode
from core.sink import SinkNode


def generate_sensor_types(config: dict) -> List[str]:
    """
    Generate sensor types according to config.yaml.

    Example:
        100 temperature
        100 humidity
        100 pm25
        100 wind
        100 water_quality
    """

    sensor_types = []

    for sensor_type, quantity in config["sensor_types"].items():
        sensor_types.extend([sensor_type] * quantity)

    expected_total = config["network"]["num_sensors"]

    if len(sensor_types) != expected_total:
        raise ValueError(
            f"Sensor type count mismatch. "
            f"Expected {expected_total}, "
            f"but got {len(sensor_types)}."
        )

    return sensor_types


def deploy_sensors(config: dict) -> List[SensorNode]:
    """
    Randomly deploy sensor nodes over the simulation area.
    """

    width = config["network"]["width_m"]
    height = config["network"]["height_m"]

    num_sensors = config["network"]["num_sensors"]
    random_seed = config["network"]["random_seed"]

    initial_energy = config["sensor"]["initial_energy_j"]
    transmission_range = config["sensor"]["transmission_range_m"]

    rng = np.random.default_rng(random_seed)

    sensor_types = generate_sensor_types(config)

    # Shuffle types so sensors are randomly distributed by type.
    rng.shuffle(sensor_types)

    x_positions = rng.uniform(
        low=0,
        high=width,
        size=num_sensors
    )

    y_positions = rng.uniform(
        low=0,
        high=height,
        size=num_sensors
    )

    sensors = []

    for i in range(num_sensors):

        sensor = SensorNode(
            node_id=i + 1,

            x=float(x_positions[i]),
            y=float(y_positions[i]),

            sensor_type=sensor_types[i],

            initial_energy=initial_energy,
            remaining_energy=initial_energy,

            transmission_range=transmission_range
        )

        sensors.append(sensor)

    return sensors


def create_sink(config: dict) -> SinkNode:
    """
    Create sink node using position from config.yaml.
    """

    return SinkNode(
        x=float(config["sink"]["x"]),
        y=float(config["sink"]["y"])
    )