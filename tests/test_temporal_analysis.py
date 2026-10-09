import unittest
from datetime import datetime
import pandas as pd

from environment.temporal_analysis import (
    prepare_time_dataframe,
    hourly_statistics,
    daily_statistics,
    weekly_statistics,
    monthly_statistics
)


class TestTemporalAnalysis(unittest.TestCase):

    def setUp(self):
        records = []
        base = datetime(2026, 1, 1, 0, 0)
        # 48 hours of dummy data for 2 sensors
        for h in range(48):
            dt = base + pd.Timedelta(hours=h)
            records.append({
                "round": h + 1,
                "timestamp": dt,
                "sensor_type": "temperature",
                "value": 25.0 + (h % 5),
                "source_id": 1
            })
            records.append({
                "round": h + 1,
                "timestamp": dt,
                "sensor_type": "humidity",
                "value": 60.0 - (h % 5),
                "source_id": 2
            })
        self.df = pd.DataFrame(records)

    def test_prepare_time_dataframe(self):
        res = prepare_time_dataframe(self.df)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(res["timestamp"]))

    def test_hourly_statistics(self):
        hourly = hourly_statistics(self.df)
        self.assertFalse(hourly.empty)
        self.assertIn("mean", hourly.columns)
        self.assertIn("min", hourly.columns)
        self.assertIn("max", hourly.columns)

    def test_daily_statistics(self):
        daily = daily_statistics(self.df)
        self.assertFalse(daily.empty)
        # 48 hours = 2 days, 2 sensor types = 4 rows
        self.assertEqual(len(daily), 4)

    def test_weekly_statistics(self):
        weekly = weekly_statistics(self.df)
        self.assertFalse(weekly.empty)

    def test_monthly_statistics(self):
        monthly = monthly_statistics(self.df)
        self.assertFalse(monthly.empty)
        self.assertEqual(monthly["month"].iloc[0], "2026-01")


if __name__ == "__main__":
    unittest.main()
