"""Bounded production-composition SD/display hardware stability trial.

Copy to CIRCUITPY/code.py only for a controlled test boot. SD is enabled in
memory; settings.toml is not modified. Controller and mirror stay disabled.
"""

import gc
import os
import time

from src.app import PendantApplication
from src.config import load_config


DURATION_SECONDS = 900
HEARTBEAT_SECONDS = 30
FILESYSTEM_SECONDS = 60
MEMORY_SECONDS = 15


def _filesystem_probe(sequence):
    import os

    names = os.listdir("/sd")
    jobs = os.listdir("/sd/jobs")
    path = "/sd/.cdaprod-hil-{:04d}.tmp".format(sequence)
    name = path.rsplit("/", 1)[-1]
    if name in names:
        raise RuntimeError("refusing to overwrite existing HIL probe file")
    with open(path, "w") as probe:
        probe.write("cdaprod-sd-hil-v1-{}".format(sequence))
    with open(path, "r") as probe:
        actual = probe.read()
    expected = "cdaprod-sd-hil-v1-{}".format(sequence)
    if actual != expected:
        raise RuntimeError("SD HIL readback mismatch")
    os.remove(path)
    if name in os.listdir("/sd"):
        raise RuntimeError("SD HIL probe removal failed")
    return len(names), len(jobs)


def run(duration_seconds=DURATION_SECONDS):
    config = load_config()
    config["sd_enabled"] = True
    config["sd_write_test"] = False
    config["controller_mode"] = "disabled"
    config["mirror_enabled"] = False
    app = PendantApplication.from_config(config)
    started = time.monotonic()
    next_heartbeat = started
    next_filesystem = started
    next_memory = started
    min_free = gc.mem_free()
    probes = 0
    wifi_connected_seen = False
    last_fs = None
    try:
        print("[HIL] started: SD test override only; controller disabled")
        print("[HIL] subsystems", app.state.subsystems)
        print("[HIL] heap", gc.mem_free())
        try:
            PendantApplication.from_config(config)
        except RuntimeError as exc:
            print("[HIL] duplicate-composition guard PASS", str(exc))
        else:
            raise RuntimeError("duplicate composition was not rejected")
        if app.sd_mount is None or app.state.subsystems.get("sd") != "MOUNTED":
            raise RuntimeError("SD failed to mount")
        if app.state.subsystems.get("display") != "OK":
            raise RuntimeError("display failed to initialize")
        if app.state.subsystems.get("touch") != "OK":
            raise RuntimeError("touch failed to initialize")
        if app.state.controller_enabled:
            raise RuntimeError("controller unexpectedly enabled")
        while time.monotonic() - started < duration_seconds:
            app.poll()
            now = time.monotonic()
            if app.state.wifi_state == "CONNECTED":
                wifi_connected_seen = True
            if now >= next_filesystem:
                last_fs = _filesystem_probe(probes)
                probes += 1
                next_filesystem = now + FILESYSTEM_SECONDS
            if now >= next_memory:
                free = gc.mem_free()
                min_free = min(min_free, free)
                print("[HIL] memory free={} min={} allocated={}".format(
                    free, min_free, gc.mem_alloc()))
                next_memory = now + MEMORY_SECONDS
            if now >= next_heartbeat:
                print("[HIL] uptime={:.0f}s loops={} renders={} "
                      "touch_errors={} wifi={} network_error={} sd={} "
                      "fs={} heap={}".format(
                          now - started, app.state.loop_count,
                          app.state.render_count,
                          getattr(app.touch_manager, "consecutive_errors", 0),
                          app.state.wifi_state, app.state.network_error,
                          app.state.subsystems.get("sd"), last_fs,
                          gc.mem_free()))
                if app.sd_mount is None or not app.sd_mount.mounted:
                    raise RuntimeError("SD mount ownership lost")
                if app.state.subsystems.get("display") != "OK":
                    raise RuntimeError("display subsystem left OK state")
                if app.state.controller_enabled:
                    raise RuntimeError("controller became enabled")
                next_heartbeat = now + HEARTBEAT_SECONDS
            time.sleep(0.01)
        if not wifi_connected_seen or app.state.wifi_state != "CONNECTED":
            raise RuntimeError("Wi-Fi did not remain connected through test end")
        print("[HIL] PASS duration={}s loops={} renders={} probes={} "
              "min_heap={} final_heap={} wifi={} touch_errors={}".format(
                  duration_seconds, app.state.loop_count,
                  app.state.render_count, probes, min_free, gc.mem_free(),
                  app.state.wifi_state,
                  getattr(app.touch_manager, "consecutive_errors", 0)))
    except Exception as exc:
        print("[HIL] FAIL", type(exc).__name__, str(exc)[:120])
        raise
    finally:
        app.deinit()
        print("[HIL] teardown complete; SD mount released")


if __name__ == "__main__":
    run()
