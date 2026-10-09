import unittest
from datetime import datetime

from simulation.simulation_clock import (
    SimulationClock,
    duration_to_rounds,
    round_to_days
)


class TestSimulationClock(unittest.TestCase):

    def test_default_clock(self):
        config = {
            "simulation": {
                "time": {
                    "start_datetime": "2026-01-01 00:00:00",
                    "round_duration_minutes": 60
                }
            }
        }
        clock = SimulationClock(config)
        self.assertEqual(clock.round_duration_seconds, 3600)
        self.assertEqual(clock.rounds_per_day, 24)

        # Round 1 is start time
        dt1 = clock.datetime_for_round(1)
        self.assertEqual(dt1, datetime(2026, 1, 1, 0, 0))

        # Round 2 is +1 hour
        dt2 = clock.datetime_for_round(2)
        self.assertEqual(dt2, datetime(2026, 1, 1, 1, 0))

        # Round 25 is next day 00:00
        dt25 = clock.datetime_for_round(25)
        self.assertEqual(dt25, datetime(2026, 1, 2, 0, 0))

        # Elapsed
        self.assertEqual(clock.elapsed_seconds(24), 24 * 3600)
        self.assertAlmostEqual(clock.elapsed_days(24), 1.0)
        self.assertAlmostEqual(clock.elapsed_days(168), 7.0)

    def test_duration_to_rounds(self):
        self.assertEqual(duration_to_rounds(10, "Rounds", 24), 10)
        self.assertEqual(duration_to_rounds(1, "Days", 24), 24)
        self.assertEqual(duration_to_rounds(7, "Days", 24), 168)
        self.assertEqual(duration_to_rounds(1, "Weeks", 24), 168)
        self.assertEqual(duration_to_rounds(1, "Months", 24), 720)

    def test_round_to_days(self):
        self.assertIsNone(round_to_days(None, 24))
        self.assertAlmostEqual(round_to_days(48, 24), 2.0)


if __name__ == "__main__":
    unittest.main()
