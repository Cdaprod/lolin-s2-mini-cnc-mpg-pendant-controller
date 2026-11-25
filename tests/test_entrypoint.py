"""The CircuitPython entry point must be safe to inspect from host tooling."""

import runpy
import unittest


class EntrypointTests(unittest.TestCase):
    def test_importing_entrypoint_does_not_start_firmware_loop(self):
        namespace = runpy.run_path("code.py", run_name="pendant_code_module")
        self.assertTrue(callable(namespace["main"]))


if __name__ == "__main__":
    unittest.main()
