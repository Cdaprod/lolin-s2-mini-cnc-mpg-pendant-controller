import contextlib
import io
import unittest

from src.diagnostics import emit, input_configuration_fields


class DiagnosticsTests(unittest.TestCase):
    def test_structured_diagnostic_line_has_bounded_single_token_fields(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            emit("touch gesture", kind="swipe left", x=12, error=None)
        self.assertEqual(output.getvalue().strip(),
                         "[event] event=touch_gesture kind=swipe_left x=12")

    def test_input_configuration_reports_resolved_map_and_gates(self):
        fields = input_configuration_fields({
            "inputs_enabled": False,
            "selector_backend": "mcp23017",
            "selector_interface_verified": False,
            "mpg_a_pin": "GPIO39",
            "mpg_b_pin": "GPIO40",
            "mpg_use_rotaryio": True,
            "mpg_counts_per_detent": 4,
            "mpg_direction": -1,
            "axis_pins": {"X": "GPA0", "Y": "GPA1"},
            "axis_map": {"X": "AXIS_X", "4": "AXIS_A"},
            "multiplier_pins": {"X1": "GPA6"},
            "button_pins": {"SELECT": "GPB2"},
            "estop_observe_pin": "GPB1",
            "deadman_pin": "",
            "selector_active_low": True,
        }, False, False, 0x20)
        self.assertEqual(fields["encoder_pins"], "A:GPIO39,B:GPIO40")
        self.assertEqual(fields["axis_pins"], "X:GPA0,Y:GPA1")
        self.assertEqual(fields["axis_map"], "X:AXIS_X,4:AXIS_A")
        self.assertEqual(fields["increment_pins"], "X1:GPA6")
        self.assertEqual(fields["deadman_pin"], "unassigned")
        self.assertFalse(fields["selector_interface_verified"])
        self.assertEqual(fields["mcp23017_address"], "0x20")
