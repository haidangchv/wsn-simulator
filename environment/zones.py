import math

import pandas as pd


def create_zones(
    config: dict
) -> pd.DataFrame:

    width = float(
        config["network"][
            "width_m"
        ]
    )

    height = float(
        config["network"][
            "height_m"
        ]
    )

    zone_size = float(
        config["environment"][
            "zones"
        ][
            "zone_size_m"
        ]
    )

    columns = math.ceil(
        width / zone_size
    )

    rows = math.ceil(
        height / zone_size
    )

    records = []

    zone_number = 1

    for row in range(rows):

        for column in range(columns):

            x_min = (
                column
                * zone_size
            )

            x_max = min(
                x_min
                +
                zone_size,

                width
            )

            y_min = (
                row
                * zone_size
            )

            y_max = min(
                y_min
                +
                zone_size,

                height
            )

            records.append({

                "zone_id":
                    f"Z{zone_number:03d}",

                "row":
                    row,

                "column":
                    column,

                "x_min":
                    x_min,

                "x_max":
                    x_max,

                "y_min":
                    y_min,

                "y_max":
                    y_max,

                "center_x":
                    (
                        x_min
                        +
                        x_max
                    )
                    / 2,

                "center_y":
                    (
                        y_min
                        +
                        y_max
                    )
                    / 2
            })

            zone_number += 1

    return pd.DataFrame(
        records
    )


def find_zone_id(
    x: float,
    y: float,
    config: dict
) -> str:

    width = float(
        config["network"]["width_m"]
    )

    height = float(
        config["network"]["height_m"]
    )

    zone_size = float(
        config["environment"][
            "zones"
        ][
            "zone_size_m"
        ]
    )

    columns = math.ceil(
        width / zone_size
    )

    rows = math.ceil(
        height / zone_size
    )

    column = min(
        int(x // zone_size),
        columns - 1
    )

    row = min(
        int(y // zone_size),
        rows - 1
    )

    zone_number = (
        row
        * columns
        +
        column
        +
        1
    )

    return (
        f"Z{zone_number:03d}"
    )