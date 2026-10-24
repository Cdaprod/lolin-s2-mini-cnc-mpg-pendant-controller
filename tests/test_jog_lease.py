"""Deterministic expiry, authorization and replay tests for receiver lease."""
import unittest
from src.controller.jog_lease import JogLease


class LeaseTests(unittest.TestCase):
    def test_replay_owner_timeout_and_new_owner(self):
        now = [0.0]
        sent, stops = [], []
        lease = JogLease(lambda cmd: sent.append(cmd) or True,
                         lambda: stops.append(True), lambda: now[0])
        a, b = bytes(6), bytes((1, 2, 3, 4, 5, 6))
        def jog(owner, seq, deadman=True, session=1):
            return lease.admit(owner, session, seq, "X", .01, 300,
                               deadman=deadman, controller_idle=True)
        self.assertTrue(jog(a, 1))
        self.assertFalse(jog(a, 1))
        self.assertFalse(jog(b, 2))
        self.assertFalse(jog(a, 2, deadman=False))
        now[0] = .26
        lease.tick()
        self.assertEqual(len(stops), 1)
        self.assertFalse(lease.active)
        self.assertTrue(jog(b, 1))
        lease.revoke()
        self.assertEqual(len(stops), 2)

    def test_invalid_and_wraparound(self):
        now = [0.]
        sent = []
        lease = JogLease(lambda cmd: sent.append(cmd) or True,
                         lambda: None, lambda: now[0])
        addr = bytes((1, 2, 3, 4, 5, 6))
        self.assertFalse(lease.admit(addr, 1, 1, "X", .01, 50))
        self.assertTrue(lease.admit(addr, 1, 65535, "X", .01, 50,
                                    deadman=True, controller_idle=True))
        self.assertTrue(lease.admit(addr, 1, 0, "X", .01, 50,
                                    deadman=True, controller_idle=True))
        self.assertFalse(lease.admit(addr, 1, 65535, "X", .01, 50,
                                     deadman=True, controller_idle=True))


if __name__ == "__main__":
    unittest.main()
