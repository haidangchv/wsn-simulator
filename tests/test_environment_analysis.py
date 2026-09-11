import unittest

import pandas as pd

from environment.interpolation import (
    idw_estimate_points
)

from environment.living_quality import (
    calculate_elqi
)

from environment.scoring import (
    optimal_range_score
)

from environment.zones import (
    create_zones
)


class EnvironmentAnalysisTest(
    unittest.TestCase
):

    def test_idw_exact_point(self):

        dataframe = pd.DataFrame([
            {
                "x": 100.0,
                "y": 100.0,
                "value": 25.0
            },

            {
                "x": 200.0,
                "y": 100.0,
                "value": 35.0
            }
        ])

        result = (
            idw_estimate_points(
                dataframe=dataframe,

                target_x=[100],

                target_y=[100],

                power=2
            )
        )

        self.assertAlmostEqual(
            result[0],
            25.0
        )

    def test_optimal_score(self):

        score = (
            optimal_range_score(
                value=25,

                hard_min=15,
                ideal_min=22,
                ideal_max=30,
                hard_max=42
            )
        )

        self.assertEqual(
            score,
            100.0
        )

    def test_elqi_weighted_score(
        self
    ):

        config = {

            "environment": {

                "living_quality": {

                    "minimum_indicators_for_elqi":
                        3,

                    "weights": {
                        "temperature": 0.20,
                        "humidity": 0.15,
                        "pm25": 0.30,
                        "wind": 0.10,
                        "water_quality": 0.25
                    }
                }
            }
        }

        scores = {
            "temperature": 80,
            "humidity": 80,
            "pm25": 80,
            "wind": 80,
            "water_quality": 80
        }

        result = calculate_elqi(
            scores,
            config
        )

        self.assertAlmostEqual(
            result,
            80.0
        )

    def test_zone_count(self):

        config = {

            "network": {
                "width_m": 2000,
                "height_m": 2000
            },

            "environment": {

                "zones": {
                    "zone_size_m": 200
                }
            }
        }

        zones = create_zones(
            config
        )

        self.assertEqual(
            len(zones),
            100
        )

        self.assertEqual(
            zones.iloc[0][
                "zone_id"
            ],
            "Z001"
        )

        self.assertEqual(
            zones.iloc[-1][
                "zone_id"
            ],
            "Z100"
        )


if __name__ == "__main__":
    unittest.main()