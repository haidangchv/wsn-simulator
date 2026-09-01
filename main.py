from collections import Counter
from pathlib import Path
from visualization.topology import plot_network
import yaml

from topology.deployment import (
    create_sink,
    deploy_sensors,
)

def load_config():
    config_path = Path(__file__).parent / "config.yaml"

    with open(config_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def main():

    config = load_config()

    print("=== WSN Simulator ===")

    sensors = deploy_sensors(config)
    sink = create_sink(config)

    print()
    print("=== Network ===")

    print(f"Number of sensors: {len(sensors)}")
    print(f"Sink: {sink}")

    print()
    print("=== Sensor Types ===")

    type_counter = Counter(
        sensor.sensor_type
        for sensor in sensors
    )

    for sensor_type, quantity in type_counter.items():
        print(
            f"{sensor_type}: "
            f"{quantity}"
        )

    print()
    print("=== First 10 Sensors ===")

    for sensor in sensors[:10]:
        print(sensor)

    print()
    print("=== Visualization ===")

    plot_network(
        sensors=sensors,
        sink=sink,
        config=config
    )
    
if __name__ == "__main__":
    main()