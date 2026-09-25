#!/usr/bin/env python3
"""Reconcile settings and deploy managed CircuitPython runtime files.

Example: CIRCUITPY=/Volumes/CIRCUITPY ./deploy.sh --apply-local-settings
"""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_NAME = ".cdaprod-deploy.json"
ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$")
BOARD_PROFILES = {"", "lolin_s2_mini_v1", "xiao_esp32s3"}
DISPLAY_PROFILES = {"", "seeed_round_240"}
PROFILE_DEPENDENCIES = {
    "seeed_round_240": ("adafruit_gc9a01a",),
}
SECRET_MARKERS = ("PASSWORD", "SECRET", "TOKEN", "KEY")
WIFI_CREDENTIALS = {"CIRCUITPY_WIFI_SSID", "CIRCUITPY_WIFI_PASSWORD"}


class DeployError(RuntimeError):
    """A validation or deployment error safe to show to an operator."""


def parse_settings(path, required=False):
    """Parse the repository's flat TOML assignment schema without eval."""
    path = Path(path)
    if not path.exists():
        if required:
            raise DeployError("settings file not found: {}".format(path))
        return {}, []
    values = {}
    order = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = ASSIGNMENT.match(stripped)
        if not match:
            raise DeployError("{}:{}: unsupported TOML setting".format(
                path, number))
        key, literal = match.groups()
        if key in values:
            raise DeployError("{}:{}: duplicate key {}".format(path, number, key))
        _validate_literal(path, number, literal)
        values[key] = literal
        order.append(key)
    return values, order


def _validate_literal(path, number, literal):
    if ((literal.startswith('"') and literal.endswith('"')) or
            (literal.startswith("'") and literal.endswith("'"))):
        return
    if literal.lower() in ("true", "false"):
        return
    try:
        float(literal)
    except ValueError as exc:
        raise DeployError("{}:{}: invalid TOML scalar".format(path, number)) from exc


def literal_value(literal):
    if len(literal) >= 2 and literal[0] == literal[-1] and literal[0] in "\"'":
        return literal[1:-1]
    return literal


def is_secret(key):
    upper = key.upper()
    return key in WIFI_CREDENTIALS or any(item in upper for item in SECRET_MARKERS)


def reconcile(template_path, local_path, device_path, apply_local=False,
              apply_secrets=False):
    template, order = parse_settings(template_path, required=True)
    local, _ = parse_settings(local_path)
    device, device_order = parse_settings(device_path)
    result = {}
    actions = []
    all_keys = order + [key for key in device_order if key not in template]
    for key in all_keys:
        if key in device:
            value, action = device[key], "preserve"
            if apply_local and key in local and not is_secret(key):
                value, action = local[key], "update"
            elif apply_secrets and key in local and is_secret(key):
                value, action = local[key], "update-secret"
        elif key in local:
            value, action = local[key], "add-local"
        else:
            value, action = template[key], "add-default"
        result[key] = value
        actions.append((action, key))
    for key in local:
        if key not in template and key not in device:
            raise DeployError("repo-local setting is not in schema: {}".format(key))
    validate_profiles(result)
    return result, all_keys, actions


def validate_profiles(settings):
    board = literal_value(settings.get("MPG_BOARD_PROFILE", '""'))
    legacy = literal_value(settings.get("MPG_HARDWARE_PROFILE", '""'))
    display = literal_value(settings.get("MPG_DISPLAY_PROFILE", '""'))
    if board not in BOARD_PROFILES:
        raise DeployError("unknown board profile: {}".format(board))
    if legacy not in BOARD_PROFILES:
        raise DeployError("unknown legacy hardware profile: {}".format(legacy))
    if display not in DISPLAY_PROFILES:
        raise DeployError("unknown display profile: {}".format(display))


def render_settings(template_path, values, order):
    emitted = set()
    output = []
    for raw in Path(template_path).read_text(encoding="utf-8").splitlines():
        match = ASSIGNMENT.match(raw.strip())
        if match and match.group(1) in values:
            key = match.group(1)
            output.append("{}={}".format(key, values[key]))
            emitted.add(key)
        else:
            output.append(raw)
    extras = [key for key in order if key not in emitted]
    if extras:
        output.extend(("", "# Device settings retained outside the current schema."))
        output.extend("{}={}".format(key, values[key]) for key in extras)
    text = "\n".join(output) + "\n"
    _validate_rendered(text)
    return text


def _validate_rendered(text):
    seen = set()
    for number, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = ASSIGNMENT.match(stripped)
        if not match:
            raise DeployError("generated settings:{}: invalid assignment".format(number))
        key = match.group(1)
        if key in seen:
            raise DeployError("generated settings:{}: duplicate key {}".format(
                number, key))
        seen.add(key)


def runtime_files(root=ROOT):
    paths = [Path("code.py"), Path("patterns.py")]
    paths.extend(path.relative_to(root) for path in sorted((root / "src").rglob("*.py"))
                 if "__pycache__" not in path.parts)
    lib = root / "lib"
    if lib.exists():
        paths.extend(path.relative_to(root) for path in sorted(lib.rglob("*"))
                     if path.is_file() and path.name != "README.md" and
                     "__pycache__" not in path.parts and not path.name.startswith("."))
    return [str(path) for path in paths]


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dependency_problems(settings, root=ROOT, target=None):
    profile = literal_value(settings.get("MPG_DISPLAY_PROFILE", '""'))
    problems = []
    for module in PROFILE_DEPENDENCIES.get(profile, ()):
        candidates = ("lib/{}.mpy".format(module), "lib/{}.py".format(module),
                      "lib/{}/__init__.py".format(module),
                      "lib/{}/__init__.mpy".format(module))
        bases = [Path(root)] if root is not None else []
        if target:
            bases.append(Path(target))
        if not any((base / candidate).is_file()
                   for base in bases for candidate in candidates):
            problems.append("missing dependency {} for display profile {}".format(
                module, profile))
    return problems


def read_manifest(target):
    path = Path(target) / MANIFEST_NAME
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DeployError("invalid deployment manifest: {}".format(path)) from exc
    if not isinstance(data, dict):
        return {}
    managed = data.get("managed_files", [])
    if not isinstance(managed, list) or not all(
            isinstance(item, str) and managed_path(item) for item in managed):
        raise DeployError("deployment manifest contains an unsafe managed path")
    return data


def managed_path(relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        return False
    return (relative in ("code.py", "patterns.py") or
            (path.parts and path.parts[0] in ("src", "lib")))


def git_value(*args):
    try:
        return subprocess.check_output(
            ("git",) + args, cwd=str(ROOT), stderr=subprocess.DEVNULL,
            text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def inspect_boot(target, settings):
    boot = Path(target) / "boot_out.txt"
    if not boot.exists():
        print("warning: boot_out.txt not found; board/version not detected")
        return
    first = boot.read_text(encoding="utf-8", errors="replace").splitlines()
    summary = " | ".join(first[:2])
    print("Detected:", summary)
    board = literal_value(settings.get("MPG_BOARD_PROFILE", '""'))
    normalized = summary.lower().replace("-", " ")
    if board == "xiao_esp32s3" and not ("xiao" in normalized and "esp32" in normalized):
        print("warning: boot_out.txt does not identify the selected XIAO ESP32-S3")
    if board == "lolin_s2_mini_v1" and not ("lolin" in normalized or "s2 mini" in normalized):
        print("warning: boot_out.txt does not identify the selected LOLIN S2 Mini")


def verify(target, root=ROOT):
    target = Path(target)
    manifest = read_manifest(target)
    if not manifest:
        raise DeployError("deployment manifest not found")
    errors = []
    for relative in manifest.get("managed_files", []):
        source, deployed = Path(root) / relative, target / relative
        if not deployed.is_file():
            errors.append("missing runtime file: {}".format(relative))
        elif not source.is_file() or file_hash(source) != file_hash(deployed):
            errors.append("runtime mismatch: {}".format(relative))
    settings, _ = parse_settings(target / "settings.toml", required=True)
    validate_profiles(settings)
    errors.extend(dependency_problems(settings, root=None, target=target))
    if errors:
        raise DeployError("verification failed:\n- " + "\n- ".join(errors))
    print("Verification passed: {} managed runtime files".format(
        len(manifest.get("managed_files", []))))


def atomic_write(path, content, backup=False):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    if backup and path.exists():
        backup_path = path.with_name(path.name + ".bak")
        backup_temp = path.with_name(path.name + ".bak.tmp")
        shutil.copy2(path, backup_temp)
        try:
            os.replace(str(backup_temp), str(backup_path))
        except OSError:
            if backup_path.exists():
                backup_path.unlink()
            backup_temp.rename(backup_path)
    try:
        os.replace(str(temporary), str(path))
    except OSError:
        if path.exists():
            path.unlink()
        temporary.rename(path)


def deploy(args):
    target = Path(os.environ.get("CIRCUITPY", "/Volumes/CIRCUITPY"))
    if not target.is_dir():
        raise DeployError("CIRCUITPY drive not found: {}".format(target))
    template = ROOT / "settings.toml.example"
    local = ROOT / "settings.toml"
    device = target / "settings.toml"
    settings, order, actions = reconcile(
        template, local, device, args.apply_local_settings,
        args.apply_local_secrets)
    inspect_boot(target, settings)
    files = runtime_files()
    previous = read_manifest(target)
    stale = sorted(set(previous.get("managed_files", ())) - set(files))
    problems = dependency_problems(settings, target=target)
    for action, key in actions:
        print("settings: {:13} {}={}".format(
            action, key, "<redacted>" if is_secret(key) else settings[key]))
    for relative in files:
        destination = target / relative
        action = "preserve" if (destination.is_file() and
                                file_hash(ROOT / relative) == file_hash(destination)) else (
                                    "change" if destination.exists() else "add")
        print("runtime:  {:13} {}".format(action, relative))
    for relative in stale:
        print("runtime:  remove-managed {}".format(relative))
    for problem in problems:
        print("dependency:", problem)
    if problems:
        raise DeployError("install required CircuitPython dependencies before deployment")
    if args.dry_run:
        print("Dry run complete; no files changed.")
        return
    rendered = render_settings(template, settings, order)
    for relative in files:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".tmp")
        shutil.copy2(ROOT / relative, temporary)
        try:
            os.replace(str(temporary), str(destination))
        except OSError:
            if destination.exists():
                destination.unlink()
            temporary.rename(destination)
    for relative in stale:
        deployed = target / relative
        if deployed.is_file():
            deployed.unlink()
    atomic_write(device, rendered, backup=True)
    manifest = {
        "format": 1,
        "firmware_commit": git_value("rev-parse", "HEAD"),
        "firmware_branch": git_value("rev-parse", "--abbrev-ref", "HEAD"),
        "deployed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "board_profile": literal_value(settings.get("MPG_BOARD_PROFILE", '""')),
        "display_profile": literal_value(settings.get("MPG_DISPLAY_PROFILE", '""')),
        "managed_files": files,
    }
    atomic_write(target / MANIFEST_NAME,
                 json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    verify(target)


def parser():
    result = argparse.ArgumentParser(
        description="Safely reconcile settings and deploy CircuitPython firmware.")
    result.add_argument("--dry-run", action="store_true",
                        help="show changes without writing to CIRCUITPY")
    result.add_argument("--verify", action="store_true",
                        help="verify the mounted deployment without changing it")
    result.add_argument("--apply-local-settings", action="store_true",
                        help="override device non-secret values from ./settings.toml")
    result.add_argument("--apply-local-secrets", action="store_true",
                        help="also override protected values from ./settings.toml")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    if args.apply_local_secrets:
        args.apply_local_settings = True
    try:
        target = Path(os.environ.get("CIRCUITPY", "/Volumes/CIRCUITPY"))
        if args.verify:
            if not target.is_dir():
                raise DeployError("CIRCUITPY drive not found: {}".format(target))
            verify(target)
        else:
            deploy(args)
    except (DeployError, OSError) as exc:
        print("deploy error: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
