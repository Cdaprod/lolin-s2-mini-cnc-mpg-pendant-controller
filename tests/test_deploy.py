import contextlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools import deploy


TEMPLATE = '''# schema
MPG_HARDWARE_PROFILE=""
MPG_BOARD_PROFILE=""
MPG_DISPLAY_PROFILE=""
MPG_DISPLAY_ENABLED="false"
CIRCUITPY_WIFI_SSID=""
CIRCUITPY_WIFI_PASSWORD=""
MPG_HOSTNAME="cdaprod-cnc-pendant"
MPG_NEW_SETTING="default"
'''


class ReconciliationTests(unittest.TestCase):
    def fixture(self, local="", device=""):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "template.toml").write_text(TEMPLATE, encoding="utf-8")
        if local:
            (root / "local.toml").write_text(local, encoding="utf-8")
        if device:
            (root / "device.toml").write_text(device, encoding="utf-8")
        self.addCleanup(temporary.cleanup)
        return root

    def reconcile(self, root, apply=False, secrets=False):
        return deploy.reconcile(root / "template.toml", root / "local.toml",
                                root / "device.toml", apply, secrets)

    def test_blank_device_receives_complete_schema(self):
        root = self.fixture()
        values, order, actions = self.reconcile(root)
        self.assertEqual(set(values), set(deploy.parse_settings(
            root / "template.toml")[0]))
        self.assertTrue(all(action == "add-default" for action, _ in actions))
        rendered = deploy.render_settings(root / "template.toml", values, order)
        self.assertEqual(rendered.count("MPG_NEW_SETTING="), 1)

    def test_tracked_schema_covers_direct_configuration_keys(self):
        source = (deploy.ROOT / "src/config.py").read_text(encoding="utf-8")
        consumed = set(re.findall(
            r'_get(?:_int|_float|_bool)?\(\s*"([A-Z0-9_]+)"', source))
        # Prefix-based maps are represented by their expanded settings.
        consumed = {key for key in consumed if not key.endswith("_")}
        schema = deploy.parse_settings(
            deploy.ROOT / "settings.toml.example", required=True)[0]
        self.assertEqual(consumed - set(schema), set())

    def test_device_values_and_wifi_credentials_survive(self):
        root = self.fixture(
            local='MPG_HOSTNAME="local"\nCIRCUITPY_WIFI_PASSWORD="new"\n',
            device='MPG_HOSTNAME="device"\nCIRCUITPY_WIFI_SSID="Shop"\n'
                   'CIRCUITPY_WIFI_PASSWORD="secret"\n')
        values, _, _ = self.reconcile(root)
        self.assertEqual(values["MPG_HOSTNAME"], '"device"')
        self.assertEqual(values["CIRCUITPY_WIFI_SSID"], '"Shop"')
        self.assertEqual(values["CIRCUITPY_WIFI_PASSWORD"], '"secret"')
        self.assertEqual(values["MPG_NEW_SETTING"], '"default"')

    def test_local_populates_missing_and_explicit_sync_updates_non_secret(self):
        root = self.fixture(local='MPG_HOSTNAME="local"\n',
                            device='MPG_HOSTNAME="device"\n')
        values, _, _ = self.reconcile(root)
        self.assertEqual(values["MPG_HOSTNAME"], '"device"')
        values, _, _ = self.reconcile(root, apply=True)
        self.assertEqual(values["MPG_HOSTNAME"], '"local"')
        root = self.fixture(local='MPG_BOARD_PROFILE="xiao_esp32s3"\n')
        values, _, _ = self.reconcile(root)
        self.assertEqual(values["MPG_BOARD_PROFILE"], '"xiao_esp32s3"')

    def test_secret_sync_requires_separate_authorization(self):
        root = self.fixture(local='CIRCUITPY_WIFI_PASSWORD="new"\n',
                            device='CIRCUITPY_WIFI_PASSWORD="old"\n')
        values, _, _ = self.reconcile(root, apply=True)
        self.assertEqual(values["CIRCUITPY_WIFI_PASSWORD"], '"old"')
        values, _, _ = self.reconcile(root, apply=True, secrets=True)
        self.assertEqual(values["CIRCUITPY_WIFI_PASSWORD"], '"new"')

    def test_duplicate_and_malformed_settings_fail(self):
        root = self.fixture(device='MPG_HOSTNAME="one"\nMPG_HOSTNAME="two"\n')
        with self.assertRaises(deploy.DeployError):
            self.reconcile(root)
        root = self.fixture(device='this is not TOML\n')
        before = (root / "device.toml").read_bytes()
        with self.assertRaises(deploy.DeployError):
            self.reconcile(root)
        self.assertEqual((root / "device.toml").read_bytes(), before)

    def test_supported_profiles_are_independent_and_legacy_is_not_default(self):
        for board, display in (("xiao_esp32s3", "seeed_round_240"),
                               ("xiao_esp32s3", ""),
                               ("lolin_s2_mini_v1", "")):
            root = self.fixture(local=(
                'MPG_BOARD_PROFILE="{}"\nMPG_DISPLAY_PROFILE="{}"\n'.format(
                    board, display)))
            values, _, _ = self.reconcile(root)
            self.assertEqual(deploy.literal_value(values["MPG_BOARD_PROFILE"]),
                             board)
            self.assertEqual(deploy.literal_value(values["MPG_DISPLAY_PROFILE"]),
                             display)
        defaults = deploy.parse_settings(root / "template.toml")[0]
        self.assertEqual(defaults["MPG_HARDWARE_PROFILE"], '""')

    def test_round_display_dependency_inventory_is_enforced(self):
        settings = {"MPG_DISPLAY_PROFILE": '"seeed_round_240"'}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertTrue(deploy.dependency_problems(settings, root=root))
            (root / "lib").mkdir()
            (root / "lib/adafruit_gc9a01a.mpy").write_bytes(b"driver")
            self.assertEqual(deploy.dependency_problems(settings, root=root), [])

    def test_enabled_touch_requires_cst8xx_dependency(self):
        settings = {"MPG_DISPLAY_PROFILE": '""',
                    "MPG_TOUCH_ENABLED": "true"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertIn("adafruit_cst8xx",
                          deploy.dependency_problems(settings, root=root)[0])
            (root / "lib").mkdir()
            (root / "lib/adafruit_cst8xx.mpy").write_bytes(b"driver")
            self.assertEqual(deploy.dependency_problems(settings, root=root), [])


class DeploymentCLITests(unittest.TestCase):
    def run_cli(self, target, *arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {"CIRCUITPY": str(target)}), \
                patch.object(deploy, "mounted_filesystems",
                             return_value={os.path.realpath(str(target))}), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = deploy.main(list(arguments))
        return SimpleNamespace(returncode=code, stdout=stdout.getvalue(),
                               stderr=stderr.getvalue())

    @staticmethod
    def mark_circuitpython(target):
        (Path(target) / "boot_out.txt").write_text(
            "Adafruit CircuitPython 10.3.1\nSeeed XIAO ESP32S3\n",
            encoding="utf-8")

    def test_missing_circuitpy_fails_safely(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing"
            result = self.run_cli(missing, "--dry-run")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("drive not found", result.stderr)

    def test_dry_run_makes_no_changes_and_redacts_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            self.mark_circuitpython(target)
            settings = target / "settings.toml"
            settings.write_text('CIRCUITPY_WIFI_PASSWORD="TopSecret"\n',
                                encoding="utf-8")
            before = settings.read_bytes()
            result = self.run_cli(target, "--dry-run")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(settings.read_bytes(), before)
            self.assertNotIn("TopSecret", result.stdout)
            self.assertIn("<redacted>", result.stdout)
            self.assertFalse((target / deploy.MANIFEST_NAME).exists())

    def test_deploy_is_idempotent_writes_backup_manifest_and_verifies(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            self.mark_circuitpython(target)
            (target / "settings.toml").write_text(
                'CIRCUITPY_WIFI_SSID="Shop"\n'
                'CIRCUITPY_WIFI_PASSWORD="secret"\n'
                'MPG_BOARD_PROFILE="xiao_esp32s3"\n'
                'MPG_DISPLAY_PROFILE=""\n', encoding="utf-8")
            first = self.run_cli(target)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertTrue((target / "settings.toml.bak").is_file())
            manifest = json.loads((target / deploy.MANIFEST_NAME).read_text())
            self.assertIn("src/network.py", manifest["managed_files"])
            deployed = (target / "settings.toml").read_text()
            self.assertEqual(deployed.count("MPG_BOARD_PROFILE="), 1)
            self.assertIn('CIRCUITPY_WIFI_PASSWORD="secret"', deployed)
            second = self.run_cli(target)
            self.assertEqual(second.returncode, 0, second.stderr)
            verified = self.run_cli(target, "--verify")
            self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_verify_detects_missing_runtime_file_and_dependency(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            self.mark_circuitpython(target)
            (target / "settings.toml").write_text(
                'MPG_HARDWARE_PROFILE=""\nMPG_BOARD_PROFILE="xiao_esp32s3"\n'
                'MPG_DISPLAY_PROFILE="seeed_round_240"\n', encoding="utf-8")
            (target / deploy.MANIFEST_NAME).write_text(json.dumps({
                "managed_files": ["code.py"]
            }), encoding="utf-8")
            result = self.run_cli(target, "--verify")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing runtime file", result.stderr)
            self.assertIn("missing dependency", result.stderr)

    def test_manifest_cannot_remove_paths_outside_managed_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            self.mark_circuitpython(target)
            (target / deploy.MANIFEST_NAME).write_text(json.dumps({
                "managed_files": ["../settings.toml"]
            }), encoding="utf-8")
            result = self.run_cli(target, "--verify")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unsafe managed path", result.stderr)


class TargetValidationTests(unittest.TestCase):
    def volume(self, boot=True):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        target = Path(temporary.name)
        if boot:
            (target / "boot_out.txt").write_text(
                "Adafruit CircuitPython 10.3.1\n", encoding="utf-8")
        return target

    def test_genuine_mount_requires_circuitpython_identity(self):
        target = self.volume()
        self.assertEqual(deploy.validate_target(target, "Linux", {target}), target)
        with self.assertRaisesRegex(deploy.DeployError, "boot_out.txt missing"):
            missing_boot = self.volume(boot=False)
            deploy.validate_target(missing_boot, "Linux", {missing_boot})

    def test_ordinary_and_stale_directories_are_refused(self):
        target = self.volume()
        with self.assertRaisesRegex(deploy.DeployError, "ordinary or stale"):
            deploy.validate_target(target, "Linux", set())
        missing = target / "missing"
        with self.assertRaisesRegex(deploy.DeployError, "drive not found"):
            deploy.validate_target(missing, "Linux", set())

    def test_diskutil_timeout_is_bounded_and_not_confirmation(self):
        with patch.object(deploy, "_run_inspection", return_value=None):
            self.assertIsNone(deploy.diskutil_confirms_mount("/Volumes/CIRCUITPY"))

    def test_macos_stuck_state_prints_recovery_but_normal_does_not(self):
        with patch.object(deploy, "diskarbitrationd_state", return_value="Us"):
            message = deploy.mount_diagnostic("Darwin")
            self.assertIn(deploy.MACOS_RECOVERY_COMMAND, message)
        with patch.object(deploy, "diskarbitrationd_state", return_value="Ss"):
            self.assertIsNone(deploy.mount_diagnostic("Darwin"))
        with patch.object(deploy, "diskarbitrationd_state") as state:
            self.assertIsNone(deploy.mount_diagnostic("Linux"))
            state.assert_not_called()


if __name__ == "__main__":
    unittest.main()
