import unittest

from core.sensor import SensorNode
from routing.load_tracker import RelayLoadTracker


def create_sensor(
    node_id: int,
    energy: float = 2.0,
    forwarded: int = 0
) -> SensorNode:

    sensor = SensorNode(
        node_id=node_id,
        x=0.0,
        y=0.0,
        sensor_type="temperature",
        initial_energy=2.0,
        remaining_energy=energy,
        transmission_range=200.0
    )
    sensor.forwarded_packets = forwarded
    return sensor


class RelayLoadTrackerTest(
    unittest.TestCase
):

    def test_hysteresis_overload_and_recovery(
        self
    ):
        """
        Verify hysteresis:
        - When load_factor >= overload_factor (2.0) -> OVERLOADED
        - When load_factor drops to 1.6 (> 1.2) -> still OVERLOADED
        - When load_factor drops <= recovery_factor (1.2) -> RECOVERED
        """

        tracker = RelayLoadTracker(
            window_rounds=5,
            overload_factor=2.0,
            recovery_factor=1.2
        )

        sensor_a = create_sensor(1, forwarded=0)
        sensor_b = create_sensor(2, forwarded=0)
        sensor_c = create_sensor(3, forwarded=0)
        sensors = [sensor_a, sensor_b, sensor_c]

        # Round 0 init: establish baseline totals
        tracker.update(sensors)

        # Round 1 to 5:
        # Node A forwards 10 pkts/round
        # Node B forwards 100 pkts/round (hotspot)
        # Node C forwards 10 pkts/round
        for _ in range(5):
            sensor_a.forwarded_packets += 10
            sensor_b.forwarded_packets += 100
            sensor_c.forwarded_packets += 10
            tracker.update(sensors)

        # Active loads: A=50, B=500, C=50
        # Mean active load = (50 + 500 + 50) / 3 = 200.0
        # B load factor = 500 / 200 = 2.5 >= 2.0 -> B is OVERLOADED
        self.assertAlmostEqual(
            tracker.get_load_factor(2),
            2.5,
            places=2
        )
        self.assertTrue(
            tracker.is_overloaded(2)
        )
        self.assertFalse(
            tracker.is_overloaded(1)
        )
        self.assertFalse(
            tracker.is_overloaded(3)
        )

        # Next rounds: B's forwarding decreases, but remains between 1.2 and 2.0
        # Let's adjust window so B has moderate load factor (e.g. 1.6)
        # We can push 5 rounds with:
        # A=25, B=64, C=25
        # Total in window: A=125, B=320, C=125
        # Mean = (125 + 320 + 125) / 3 = 190.0
        # B load factor = 320 / 190 = 1.684
        for _ in range(5):
            sensor_a.forwarded_packets += 25
            sensor_b.forwarded_packets += 64
            sensor_c.forwarded_packets += 25
            tracker.update(sensors)

        b_factor = tracker.get_load_factor(2)
        self.assertTrue(
            1.2 < b_factor < 2.0,
            f"Expected B load factor between 1.2 and 2.0, got {b_factor}"
        )
        # B must STILL be OVERLOADED due to hysteresis!
        self.assertTrue(
            tracker.is_overloaded(2),
            "Node B should remain OVERLOADED when load is between recovery and overload threshold"
        )

        # Next rounds: B's forwarding drops down to normal (<= 1.2)
        # A=50, B=20, C=50
        for _ in range(5):
            sensor_a.forwarded_packets += 50
            sensor_b.forwarded_packets += 20
            sensor_c.forwarded_packets += 50
            tracker.update(sensors)

        b_factor_recovered = tracker.get_load_factor(2)
        self.assertTrue(
            b_factor_recovered <= 1.2,
            f"Expected B load factor <= 1.2, got {b_factor_recovered}"
        )
        # B must now RECOVER (not overloaded)
        self.assertFalse(
            tracker.is_overloaded(2),
            "Node B should recover once load factor <= 1.2"
        )

    def test_metrics_calculation(
        self
    ):

        tracker = RelayLoadTracker(
            window_rounds=5,
            overload_factor=2.0,
            recovery_factor=1.2
        )

        sensor_a = create_sensor(1, forwarded=0)
        sensor_b = create_sensor(2, forwarded=0)
        sensors = [sensor_a, sensor_b]

        tracker.update(sensors)

        sensor_a.forwarded_packets += 20
        sensor_b.forwarded_packets += 40
        tracker.update(sensors)

        metrics = tracker.get_metrics()
        self.assertEqual(
            metrics["active_relay_count"],
            2
        )
        self.assertEqual(
            metrics["mean_relay_load"],
            30.0
        )
        self.assertEqual(
            metrics["max_relay_load"],
            40
        )
        self.assertGreater(
            metrics["relay_load_cv"],
            0.0
        )


if __name__ == "__main__":
    unittest.main()
