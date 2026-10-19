import unittest
import math
from copy import deepcopy

from core.network import WirelessSensorNetwork
from core.sink import SinkNode
from core.sensor import SensorNode
from mobility.sink_stress_monitor import SinkStressMonitor, SinkStressSnapshot
from mobility.adaptive_sink import AdaptiveSinkController, Waypoint, SinkDecision
from routing.route_manager import RouteManager
from simulation.simulator import WSNSimulator
from topology.deployment import deploy_sensors, create_sink
import yaml


class AdaptiveSinkTest(unittest.TestCase):

    def setUp(self):
        with open("config.yaml", "r", encoding="utf-8") as f:
            self.base_config = yaml.safe_load(f)

        self.config = deepcopy(self.base_config)
        # Use small test configuration with 800x800 area
        self.config["network"]["num_sensors"] = 50
        self.config["sensor_types"] = {
            "temperature": 10,
            "humidity": 10,
            "pm25": 10,
            "wind": 10,
            "water_quality": 10
        }
        self.config["network"]["width_m"] = 800.0
        self.config["network"]["height_m"] = 800.0
        self.config["sink"]["x"] = 400.0
        self.config["sink"]["y"] = 400.0
        self.config["sensor"]["transmission_range_m"] = 250.0
        self.config["routing"]["algorithm"] = "ecmhr"

        # Cấu hình dynamic candidate cho map 800x800
        self.config["mobile_sink"]["candidate_radii_m"] = [150.0, 200.0, 250.0]
        self.config["mobile_sink"]["min_move_distance_m"] = 150.0
        self.config["mobile_sink"]["max_move_distance_m"] = 300.0
        self.config["mobile_sink"]["boundary_margin_m"] = 50.0
        self.config["mobile_sink"]["tabu_radius_m"] = 100.0
        self.config["mobile_sink"]["return_tabu_rounds"] = 72
        self.config["mobile_sink"]["minimum_improvement_ratio"] = 0.05

        sensors = deploy_sensors(self.config)
        sink = create_sink(self.config)
        self.network = WirelessSensorNetwork(sensors=sensors, sink=sink)
        self.network.build_topology()

        self.route_manager = RouteManager(
            network=self.network,
            config=self.config,
            algorithm="ecmhr"
        )

    def test_dynamic_candidate_generation(self):
        controller = AdaptiveSinkController(
            network=self.network,
            config=self.config
        )
        candidates = controller.generate_dynamic_candidates(
            cur_x=400.0,
            cur_y=400.0,
            current_round=0
        )
        self.assertGreater(len(candidates), 0)
        self.assertLessEqual(len(candidates), 36)

        # Kiểm tra miền an toàn (boundary_margin_m = 50)
        for c in candidates:
            self.assertGreaterEqual(c.x, 50.0)
            self.assertLessEqual(c.x, 750.0)
            self.assertGreaterEqual(c.y, 50.0)
            self.assertLessEqual(c.y, 750.0)

            # Kiểm tra khoảng cách di chuyển
            dist = math.hypot(c.x - 400.0, c.y - 400.0)
            self.assertGreaterEqual(dist, 149.0)
            self.assertLessEqual(dist, 301.0)

    def test_tabu_filtering(self):
        controller = AdaptiveSinkController(
            network=self.network,
            config=self.config
        )
        base_candidates = controller.generate_dynamic_candidates(400.0, 400.0, 0)
        self.assertGreater(len(base_candidates), 0)

        # Chọn 1 candidate làm vị trí tabu
        target_cand = base_candidates[0]
        controller.tabu_history.append((target_cand.x, target_cand.y, 10))

        # Tại round 20 (< 10 + 72 = 82): candidate gần vị trí tabu phải bị loại
        cand_tabu = controller.generate_dynamic_candidates(400.0, 400.0, 20)
        self.assertLess(len(cand_tabu), len(base_candidates))
        for c in cand_tabu:
            d_tabu = math.hypot(c.x - target_cand.x, c.y - target_cand.y)
            self.assertGreaterEqual(d_tabu, controller.tabu_radius_m)

        # Tại round 90 (>= 82): tabu hết hạn, candidate được phép phục hồi
        cand_expired = controller.generate_dynamic_candidates(400.0, 400.0, 90)
        self.assertEqual(len(cand_expired), len(base_candidates))

    def test_stress_monitor_evaluation(self):
        monitor = SinkStressMonitor(
            network=self.network,
            load_window_rounds=24,
            overload_factor=1.8,
            overloaded_ratio_threshold=0.30,
            drain_ratio_threshold=1.50,
            route_concentration_threshold=0.30,
            monitor_hops=1
        )

        near_sink = monitor.get_near_sink_relays()
        self.assertGreater(len(near_sink), 0)

        # Round 1 evaluation with empty traffic
        self.route_manager.prepare_round(1)
        snap = monitor.evaluate(1, self.route_manager.route_table)
        self.assertIsInstance(snap, SinkStressSnapshot)
        self.assertFalse(snap.should_alert)

        sensor_map = {s.node_id: s for s in self.network.sensors}
        for r in range(1, 10):
            # Baseline traffic across network
            for sensor in self.network.sensors:
                sensor.forwarded_packets += 2
                sensor.consume_energy(0.002, 0.001)

            # Heavy stress on near-sink relays
            for node_id in near_sink:
                sensor = sensor_map[node_id]
                sensor.forwarded_packets += 50
                sensor.consume_energy(0.2, 0.1)

            monitor.record_round(r)

        snap2 = monitor.evaluate(10, self.route_manager.route_table)
        self.assertGreaterEqual(snap2.active_alerts_count, 1)

    def test_controller_stay_and_move_lifecycle(self):
        controller = AdaptiveSinkController(
            network=self.network,
            config=self.config
        )
        controller.evaluation_interval_rounds = 6
        controller.trigger_persistence = 2
        controller.minimum_dwell_rounds = 0

        # Giả lập cảnh báo stress
        alert_snapshot = SinkStressSnapshot(
            round_number=6,
            near_sink_nodes_count=5,
            stressed_relays_count=3,
            overloaded_ratio=0.60,
            drain_ratio=2.0,
            max_route_concentration=0.40,
            alert_load=True,
            alert_drain=True,
            alert_concentration=True,
            active_alerts_count=3,
            should_alert=True
        )
        controller.stress_monitor.evaluate = lambda *args, **kwargs: alert_snapshot

        # Giả lập load nặng trên các relay gần vị trí Sink hiện tại
        near_sink = controller.stress_monitor.get_near_sink_relays()
        for nid in near_sink:
            controller.stress_monitor.forwarded_history[nid] = [100] * 24

        # Check 1 (round 6): 1 consecutive alert -> stay (persistence requires 2)
        decision1 = controller.evaluate_and_step(6, self.route_manager)
        self.assertTrue(decision1.evaluated)
        self.assertFalse(decision1.moved)
        self.assertEqual(controller.consecutive_alerts, 1)

        # Check 2 (round 12): 2 consecutive alerts -> MOVE!
        decision2 = controller.evaluate_and_step(12, self.route_manager)
        self.assertTrue(decision2.evaluated)
        self.assertTrue(decision2.moved)
        self.assertGreater(decision2.distance_m, 0.0)

        # Verify Sink position updated
        self.assertEqual(self.network.sink.x, decision2.to_pos[0])
        self.assertEqual(self.network.sink.y, decision2.to_pos[1])
        self.assertEqual(self.network.sink.movement_count, 1)

        # Verify old position is stored in Tabu history
        self.assertEqual(len(controller.tabu_history), 1)
        self.assertEqual(controller.tabu_history[0][0], decision2.from_pos[0])
        self.assertEqual(controller.tabu_history[0][1], decision2.from_pos[1])

    def test_dwell_time_prevents_premature_move(self):
        controller = AdaptiveSinkController(
            network=self.network,
            config=self.config
        )
        controller.evaluation_interval_rounds = 6
        controller.minimum_dwell_rounds = 24
        controller.trigger_persistence = 1

        alert_snapshot = SinkStressSnapshot(
            round_number=6,
            near_sink_nodes_count=5,
            stressed_relays_count=3,
            overloaded_ratio=0.60,
            drain_ratio=2.0,
            max_route_concentration=0.40,
            alert_load=True,
            alert_drain=True,
            alert_concentration=True,
            active_alerts_count=3,
            should_alert=True
        )
        controller.stress_monitor.evaluate = lambda *args, **kwargs: alert_snapshot

        # Giả lập load nặng
        near_sink = controller.stress_monitor.get_near_sink_relays()
        for nid in near_sink:
            controller.stress_monitor.forwarded_history[nid] = [100] * 24

        # Cho phép move lần đầu ở round 6
        controller.last_move_round = -100
        decision1 = controller.evaluate_and_step(6, self.route_manager)
        self.assertTrue(decision1.moved)
        self.assertEqual(controller.last_move_round, 6)

        # Tại round 12 (6 rounds sau < 24 dwell rounds): Sink bắt buộc phải STAY
        decision2 = controller.evaluate_and_step(12, self.route_manager)
        self.assertFalse(decision2.moved)
        self.assertIn("in_dwell", decision2.reason)

    def test_minimum_improvement_threshold(self):
        controller = AdaptiveSinkController(
            network=self.network,
            config=self.config
        )
        controller.evaluation_interval_rounds = 6
        controller.minimum_dwell_rounds = 0
        controller.trigger_persistence = 1
        controller.minimum_improvement_ratio = 0.50  # Ngưỡng cải thiện cao 50%

        alert_snapshot = SinkStressSnapshot(
            round_number=6,
            near_sink_nodes_count=5,
            stressed_relays_count=3,
            overloaded_ratio=0.60,
            drain_ratio=2.0,
            max_route_concentration=0.40,
            alert_load=True,
            alert_drain=True,
            alert_concentration=True,
            active_alerts_count=3,
            should_alert=True
        )
        controller.stress_monitor.evaluate = lambda *args, **kwargs: alert_snapshot

        # Mock score candidates sao cho candidate tốt hơn nhưng chỉ cải thiện 5% (< 50%)
        dummy_wp = Waypoint(idx=1, x=450.0, y=450.0, name="C1")
        controller._dry_run_score_candidates = lambda *args, **kwargs: (
            dummy_wp, 0.50, 0.475, 0.05
        )

        decision = controller.evaluate_and_step(6, self.route_manager)
        self.assertTrue(decision.evaluated)
        self.assertFalse(decision.moved)
        self.assertIn("Improvement", decision.reason)

    def test_full_simulator_integration(self):
        sim = WSNSimulator(
            network=self.network,
            config=self.config,
            routing_algorithm="ecmhr"
        )
        self.assertIsNotNone(sim.sink_controller)
        self.assertTrue(sim.mobile_sink_enabled)

        # Run 12 rounds
        sim.run(rounds=12)
        metrics = sim.get_metrics()
        self.assertIn("sink_x", metrics)
        self.assertIn("sink_y", metrics)
        self.assertIn("sink_waypoint", metrics)
        self.assertIn("sink_movement_count", metrics)
        self.assertIn("near_sink_overloaded_ratio", metrics)
        self.assertIn("near_sink_drain_ratio", metrics)
        self.assertIn("max_route_concentration", metrics)


if __name__ == "__main__":
    unittest.main()
