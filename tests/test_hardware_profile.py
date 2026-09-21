import os
import unittest
from unittest.mock import patch

from src.config import load_config
from src.hardware_profiles import LOLIN_S2_MINI_V1, apply_hardware_profile
from src.input.mcp23017 import MCP23017InputBank


class HardwareProfileTests(unittest.TestCase):
    def test_reference_profile_fills_proposed_pins_without_enabling_hardware(self):
        with patch.dict(os.environ, {
            "MPG_HARDWARE_PROFILE": LOLIN_S2_MINI_V1,
            "MPG_INPUTS_ENABLED": "false",
            "MPG_DISPLAY_ENABLED": "false",
            "MPG_SD_ENABLED": "false",
        }, clear=True):
            config = load_config()
        self.assertEqual(config["mpg_a_pin"], "IO1")
        self.assertEqual(config["mpg_b_pin"], "IO2")
        self.assertEqual(config["uart_tx_pin"], "IO17")
        self.assertEqual(config["uart_rx_pin"], "IO18")
        self.assertEqual(config["i2c_sda_pin"], "IO33")
        self.assertEqual(config["i2c_scl_pin"], "IO35")
        self.assertEqual(config["sd_sck_pin"], "IO7")
        self.assertEqual(config["sd_mosi_pin"], "IO11")
        self.assertEqual(config["sd_miso_pin"], "IO9")
        self.assertEqual(config["display_cs_pin"], "IO12")
        self.assertEqual(config["display_dc_pin"], "IO13")
        self.assertEqual(config["button_pins"]["CANCEL"], "IO5")
        self.assertEqual(config["selector_backend"], "mcp23017")
        self.assertFalse(config["inputs_enabled"])
        self.assertFalse(config["display_enabled"])
        self.assertFalse(config["sd_enabled"])
        self.assertFalse(config["selector_interface_verified"])

    def test_explicit_assignment_overrides_profile(self):
        config = apply_hardware_profile({
            "hardware_profile": LOLIN_S2_MINI_V1,
            "mpg_a_pin": "CUSTOM_A",
            "button_pins": {"SELECT": "CUSTOM_SELECT"},
        })
        self.assertEqual(config["mpg_a_pin"], "CUSTOM_A")
        self.assertEqual(config["button_pins"]["SELECT"], "CUSTOM_SELECT")
        self.assertEqual(config["button_pins"]["FN"], "IO6")

    def test_unknown_profile_fails_closed(self):
        with self.assertRaises(ValueError):
            apply_hardware_profile({"hardware_profile": "unknown"})


class FakeI2C:
    def __init__(self):
        self.locked = False
        self.writes = []
        self.gpio = (0xFE, 0xFE)

    def try_lock(self):
        if self.locked:
            return False
        self.locked = True
        return True

    def unlock(self):
        self.locked = False

    def writeto(self, address, data):
        self.writes.append((address, bytes(data)))

    def writeto_then_readfrom(self, address, output, target):
        self.writes.append((address, bytes(output)))
        target[0], target[1] = self.gpio


class MCP23017Tests(unittest.TestCase):
    def test_input_bank_configures_pullups_and_caches_one_snapshot(self):
        i2c = FakeI2C()
        bank = MCP23017InputBank(i2c, 0x20, 0x01FF)
        self.assertEqual(i2c.writes[0], (0x20, b"\x00\xff\xff"))
        self.assertEqual(i2c.writes[1], (0x20, b"\x0c\xff\x01"))
        self.assertTrue(bank.refresh())
        self.assertFalse(bank.pin(0).value)
        self.assertTrue(bank.pin(1).value)
        self.assertFalse(bank.pin(8).value)

    def test_busy_bus_keeps_safe_cached_high_state(self):
        i2c = FakeI2C()
        bank = MCP23017InputBank(i2c)
        i2c.locked = True
        self.assertFalse(bank.refresh())
        self.assertEqual(bank.value, 0xFFFF)
        self.assertEqual(bank.read_errors, 1)


if __name__ == "__main__":
    unittest.main()
