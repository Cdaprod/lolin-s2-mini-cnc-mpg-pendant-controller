import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from src.config import load_config
from src.hardware_profiles import (LOLIN_S2_MINI_V1, SEEED_ROUND_240,
                                   XIAO_ESP32S3, apply_hardware_profile)
from src.input.circuitpython import (CircuitPythonInputAdapter, from_config,
                                     resolve_native_pin)
from src.input.mcp23017 import (MCP23017InputBank, parse_virtual_pin,
                                virtual_pin_name)


class HardwareProfileTests(unittest.TestCase):
    def test_example_config_maps_selector_four_to_a_axis(self):
        template = Path(__file__).resolve().parents[1] / "settings.toml.example"
        values = {}
        for line in template.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"')
        self.assertEqual(values["MPG_AXIS_MAP_4"], "AXIS_A")

    def test_current_environment_defaults_and_invalid_address(self):
        with patch.dict(os.environ, {
            "MPG_BOARD_PROFILE": XIAO_ESP32S3,
            "MPG_DISPLAY_PROFILE": SEEED_ROUND_240,
            "MPG_MCP23017_ADDRESS": "32",
        }, clear=True):
            config = load_config()
        self.assertEqual((config["mpg_a_pin"], config["mpg_b_pin"]),
                         ("GPIO39", "GPIO40"))
        self.assertEqual(config["mcp23017_address"], 0x20)
        self.assertEqual(config["sd_cs_pin"], "D2")
        self.assertEqual(config["axis_map"]["4"], "AXIS_A")
        self.assertFalse(config["inputs_enabled"])
        self.assertFalse(config["selector_interface_verified"])
        for address in ("not-an-address", "31", "40"):
            with self.subTest(address=address), patch.dict(os.environ, {
                    "MPG_MCP23017_ADDRESS": address}, clear=True):
                with self.assertRaises(ValueError):
                    load_config()

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

    def test_board_and_display_profiles_are_independent(self):
        config = apply_hardware_profile({
            "board_profile": XIAO_ESP32S3,
            "display_profile": SEEED_ROUND_240,
            "display_enabled": True,
        })
        self.assertNotIn("uart_tx_pin", config)
        self.assertEqual(config["mpg_a_pin"], "GPIO39")
        self.assertEqual(config["mpg_b_pin"], "GPIO40")
        self.assertEqual(config["axis_pins"]["X"], "GPA0")
        self.assertEqual(config["multiplier_pins"]["X100"], "GPB0")
        self.assertEqual(config["estop_observe_pin"], "GPB1")
        self.assertEqual(config["button_pins"]["SELECT"], "GPB2")
        self.assertEqual(config["display_driver"], "gc9a01")
        self.assertEqual(config["display_renderer"], "round")
        self.assertEqual(config["display_width"], 240)
        self.assertEqual(config["display_sck_pin"], "D8")
        self.assertEqual(config["i2c_sda_pin"], "D4")
        self.assertEqual(config["i2c_scl_pin"], "D5")

    def test_display_profile_can_bind_to_another_board(self):
        config = apply_hardware_profile({
            "board_profile": LOLIN_S2_MINI_V1,
            "display_profile": SEEED_ROUND_240,
            "display_enabled": True,
            "display_sck_pin": "IO7", "display_mosi_pin": "IO11",
            "display_cs_pin": "IO12", "display_dc_pin": "IO13",
        })
        self.assertEqual(config["display_sck_pin"], "IO7")
        self.assertEqual(config["display_renderer"], "round")


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
    def test_all_virtual_names_round_trip_and_invalid_names_fail(self):
        names = ["GP{}{}".format(bank, bit)
                 for bank in ("A", "B") for bit in range(8)]
        self.assertEqual([virtual_pin_name(parse_virtual_pin(name))
                          for name in names], names)
        for invalid in ("", "GPA8", "GPC0", "GPIO42", "GPA00"):
            with self.assertRaises(ValueError):
                parse_virtual_pin(invalid)

    def test_address_range_is_enforced(self):
        for address in (0x20, 0x27):
            self.assertEqual(MCP23017InputBank(FakeI2C(), address).address,
                             address)
        for address in (0x1F, 0x28):
            with self.assertRaises(ValueError):
                MCP23017InputBank(FakeI2C(), address)

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


class CircuitPythonInputFailureTests(unittest.TestCase):
    class Pin:
        def __init__(self, value):
            self.value = value

    class Encoder:
        position = 10

    def test_failed_mcp_refresh_never_returns_cached_motion_inputs(self):
        i2c = FakeI2C()
        i2c.gpio = (0x08, 0xFF)  # X, X10, SELECT, and deadman active-low.
        bank = MCP23017InputBank(i2c, pullup_mask=0x001F)
        adapter = CircuitPythonInputAdapter(
            inputs={},
            axis_inputs={"X": bank.resolve("GPA0")},
            multiplier_inputs={"X10": bank.resolve("GPA1")},
            button_inputs={"SELECT": bank.resolve("GPA2")},
            estop_input=bank.resolve("GPA3"),
            deadman_input=bank.resolve("GPA4"),
            encoder=self.Encoder(), selector_refresh=bank.refresh,
        )
        healthy = adapter.read()
        self.assertTrue(healthy.valid)
        self.assertEqual(healthy.axes, ("X",))
        self.assertEqual(healthy.multipliers, ("X10",))
        self.assertTrue(healthy.buttons["SELECT"])
        self.assertTrue(healthy.deadman)
        self.assertFalse(healthy.estop)

        i2c.locked = True
        sample = adapter.read()
        self.assertFalse(sample.valid)
        self.assertEqual(sample.valid_reason, "mcp23017_read_failed")
        self.assertEqual(sample.axes, ())
        self.assertEqual(sample.multipliers, ())
        self.assertEqual(sample.buttons, {"SELECT": False})
        self.assertFalse(sample.deadman)
        self.assertTrue(sample.estop)
        self.assertEqual(sample.mpg_delta, 0)


class CurrentPendantInputTests(unittest.TestCase):
    def setUp(self):
        self.board = types.ModuleType("board")
        self.board.GPIO39 = object()
        self.board.GPIO40 = object()
        self.digitalio = types.ModuleType("digitalio")
        self.digitalio.Direction = types.SimpleNamespace(INPUT="input")
        self.digitalio.Pull = types.SimpleNamespace(UP="up", DOWN="down")
        self.digitalio.DigitalInOut = lambda pin: types.SimpleNamespace(
            pin=pin, direction=None, pull=None, value=True)
        microcontroller = types.ModuleType("microcontroller")
        microcontroller.pin = types.SimpleNamespace(
            GPIO39=self.board.GPIO39, GPIO40=self.board.GPIO40)
        self.rotaryio = types.ModuleType("rotaryio")
        self.rotaryio.IncrementalEncoder = lambda a, b, divisor=1: \
            types.SimpleNamespace(a=a, b=b, divisor=divisor, position=0)
        self.modules = patch.dict(sys.modules, {
            "board": self.board, "digitalio": self.digitalio,
            "rotaryio": self.rotaryio,
            "microcontroller": microcontroller,
        })
        self.modules.start()

    def tearDown(self):
        self.modules.stop()

    def config(self, verified=True):
        return {
            "inputs_enabled": True, "selector_backend": "mcp23017",
            "selector_interface_verified": verified,
            "mpg_a_pin": "GPIO39", "mpg_b_pin": "GPIO40",
            "mpg_use_rotaryio": True, "mcp23017_address": 32,
            "i2c_sda_pin": "D4", "i2c_scl_pin": "D5",
            "axis_pins": {"X": "GPA0", "Y": "GPA1", "Z": "GPA2",
                          "4": "GPA3", "5": "GPA4", "6": "GPA5"},
            "multiplier_pins": {"X1": "GPA6", "X10": "GPA7",
                                "X100": "GPB0"},
            "estop_observe_pin": "GPB1",
            "button_pins": {"SELECT": "GPB2", "BACK": "GPB3",
                            "FN": "GPB4", "CANCEL": "GPB5"},
            "deadman_pin": "GPB6", "selector_active_low": True,
            "button_active_low": True, "estop_active_low": True,
            "deadman_active_low": True,
        }

    def test_native_resolution_does_not_accept_virtual_pins(self):
        self.assertIs(resolve_native_pin(self.board, "GPIO39"),
                      self.board.GPIO39)
        self.assertIs(resolve_native_pin(self.board, "GPIO40"),
                      self.board.GPIO40)
        with self.assertRaises(ValueError):
            resolve_native_pin(self.board, "GPA0")
        with self.assertRaises(ValueError):
            resolve_native_pin(self.board, "GPIO99")

    def test_disabled_and_unverified_inputs_do_not_touch_hardware(self):
        config = self.config(False)
        self.assertIsNone(from_config(config, FakeI2C()))
        config["inputs_enabled"] = False
        config["selector_interface_verified"] = True
        self.assertIsNone(from_config(config, FakeI2C()))

    def test_shared_mcp_backend_reads_all_current_active_low_controls(self):
        i2c = FakeI2C()
        adapter = from_config(self.config(), i2c)
        self.assertIs(adapter.resources[0].i2c, i2c)
        self.assertEqual(i2c.writes[0], (0x20, b"\x00\xff\xff"))
        self.assertEqual(i2c.writes[1], (0x20, b"\x0c\xff\x7f"))
        # Active-low GPA0 X, GPB0 x100, GPB1 remote stop, GPB2 SELECT.
        i2c.gpio = (0xFE, 0xF8)
        sample = adapter.read()
        self.assertEqual(sample.axes, ("X",))
        self.assertEqual(sample.multipliers, ("X100",))
        self.assertTrue(sample.estop)
        self.assertTrue(sample.buttons["SELECT"])
        self.assertFalse(sample.deadman)
        self.assertEqual((adapter.encoder.a, adapter.encoder.b),
                         (self.board.GPIO39, self.board.GPIO40))


if __name__ == "__main__":
    unittest.main()
