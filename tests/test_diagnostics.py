import contextlib
import io
import unittest

from src.diagnostics import (emit, input_configuration_fields,
                             is_runtime_reload, loop_timing_fields,
                             startup_context_fields)


class DiagnosticsTests(unittest.TestCase):
    def test_circuitpython_reload_is_distinct_from_application_failure(self):
        class ReloadException(Exception):
            pass

        self.assertTrue(is_runtime_reload(ReloadException()))
        self.assertFalse(is_runtime_reload(RuntimeError("failure")))

    def test_startup_context_reports_reload_and_reset_reasons(self):
        class Reason:
            name = "REPL_RELOAD"

        class Runtime:
            run_reason = Reason()
            safe_mode_reason = "NONE"
            serial_connected = True

        class CPU:
            reset_reason = "POWER_ON"

        class Supervisor:
            runtime = Runtime()

        class Microcontroller:
            cpu = CPU()

        self.assertEqual(startup_context_fields(Supervisor, Microcontroller), {
            "run_reason": "REPL_RELOAD",
            "safe_mode_reason": "NONE",
            "serial_connected": True,
            "reset_reason": "POWER_ON",
        })

    def test_startup_context_tolerates_missing_platform_diagnostics(self):
        class Runtime:
            pass

        class Supervisor:
            runtime = Runtime()

        self.assertEqual(startup_context_fields(Supervisor, object()), {})

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

    def test_loop_timing_reports_rate_and_unprofiled_cost(self):
        fields = loop_timing_fields(850, 9500, 10000, 5000)
        self.assertEqual(fields, {
            "loop_hz": 85,
            "poll_avg_us": 11176,
            "unprofiled_avg_us": 5294,
            "loop_window_ms": 10000,
        })
        self.assertEqual(loop_timing_fields(0, 0, 0, 0)["loop_hz"], 0)
