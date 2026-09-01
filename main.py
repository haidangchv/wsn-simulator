from pathlib import Path

import yaml


def load_config():
    config_path = Path(__file__).parent / "config.yaml"

    with open(config_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def main():
    config = load_config()

    print("=== WSN Simulator ===")

    print(
        f"Area: "
        f"{config['network']['width_m']} x "
        f"{config['network']['height_m']} m"
    )

    print(
        f"Sensors: "
        f"{config['network']['num_sensors']}"
    )

    print(
        f"Sink: "
        f"({config['sink']['x']}, "
        f"{config['sink']['y']})"
    )

    print(
        f"Initial energy: "
        f"{config['sensor']['initial_energy_j']} J"
    )

    print(
        f"Transmission range: "
        f"{config['sensor']['transmission_range_m']} m"
    )


if __name__ == "__main__":
    main()