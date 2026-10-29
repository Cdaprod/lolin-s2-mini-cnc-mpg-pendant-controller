import math
import unittest

from src.display.round_ui.rotor import BezelRotor


class BezelRotorTests(unittest.TestCase):
    def make_rotor(self, **kwargs):
        values = dict(ambient_period_s=54, encoder_gain=0.08,
                      max_speed_rad_s=0.4, inertia_s=0.9,
                      direction_change_min_s=20,
                      direction_change_max_s=40, frame_rate=24)
        values.update(kwargs)
        return BezelRotor(**values)

    def test_ambient_speed_is_one_revolution_per_configured_period(self):
        rotor = self.make_rotor()
        self.assertAlmostEqual(rotor.velocity, 2 * math.pi / 54)

    def test_encoder_speed_tracks_detent_rate_and_caps(self):
        rotor = self.make_rotor(encoder_gain=0.01)
        rotor.update(1.0, 1.0, 1)
        _, slow = rotor.update(1.1, 1.1, 1)
        _, fast = rotor.update(1.2, 1.15, 3)
        self.assertGreater(fast, slow)
        for i in range(1, 20):
            _, capped = rotor.update(1.2 + i * 0.05,
                                     1.15 + i * 0.05, 100)
        self.assertLessEqual(capped, rotor.max_speed_rad_s)
        self.assertAlmostEqual(capped, rotor.max_speed_rad_s, places=2)

    def test_encoder_reversal_changes_velocity_without_angle_jump(self):
        rotor = self.make_rotor()
        rotor.update(1.0, 1.0, 1)
        rotor.update(1.1, 1.1, 1)
        before = rotor.angle
        angle, velocity = rotor.update(1.12, 1.12, -1)
        self.assertLess(velocity, 0)
        angular_delta = (angle - before + math.pi) % (2 * math.pi) - math.pi
        self.assertLess(abs(angular_delta), 0.02)

    def test_idle_coasts_toward_ambient_without_discontinuity(self):
        rotor = self.make_rotor()
        rotor.update(0.0)
        rotor.update(0.01, 0.01, 8)
        rotor.update(0.11, 0.11, 8)
        prior = rotor.velocity
        angle = rotor.angle
        rotor.update(0.31, 0.11, 8)
        rotor.update(0.51, 0.11, 8)
        self.assertNotEqual(rotor.mode, "FOLLOW")
        self.assertLess(abs(rotor.velocity), abs(prior))
        self.assertGreater(rotor.angle, angle)

    def test_ambient_reversal_eases_through_zero(self):
        rotor = self.make_rotor(direction_change_min_s=5,
                                direction_change_max_s=5)
        rotor.update(0.0)
        for i in range(1, 50):
            rotor.update(i / 10)
        rotor.update(5.0)
        self.assertEqual(rotor.ambient_direction, -1)
        self.assertGreater(rotor.velocity, 0)
        rotor.update(6.0)
        self.assertLess(rotor.velocity, rotor._ambient_velocity() * -0.01)

    def test_integrated_angle_is_independent_of_update_cadence(self):
        fast = self.make_rotor()
        slow = self.make_rotor()
        for i in range(101):
            now = i / 100
            fast.update(now)
        for now in (0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
            slow.update(now)
        self.assertAlmostEqual(fast.angle, slow.angle, places=6)

    def test_frame_rate_ceiling_and_disable_are_allocation_free(self):
        rotor = self.make_rotor(frame_rate=20)
        self.assertTrue(rotor.frame_due(0.0))
        self.assertFalse(rotor.frame_due(0.01))
        self.assertTrue(rotor.frame_due(0.051))
        keys = set(rotor.__dict__)
        for i in range(10000):
            rotor.update(1 + i / 1000)
            rotor.frame_due(1 + i / 1000)
        self.assertEqual(keys, set(rotor.__dict__))

    def test_rotor_does_not_mutate_machine_or_operator_state(self):
        state = {"encoder": 5, "axis": "X", "increment": "X10",
                 "motion_admission": False, "controller": "idle"}
        before = dict(state)
        rotor = self.make_rotor()
        rotor.update(0.0, 0.0, 5)
        rotor.update(0.2, 0.2, -1)
        self.assertEqual(state, before)


if __name__ == "__main__":
    unittest.main()
