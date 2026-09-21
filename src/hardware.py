"""Central optional-hardware composition; unknown assignments stay disabled."""

from src.display.console import ConsoleDisplay
from src.display.indicator import from_config as indicator_from_config
from src.input.manager import InputManager, NullInputAdapter
from src.storage.sdcard import SDStorage


def build_inputs(config, state):
    adapter = None
    if config.get("inputs_enabled"):
        from src.input.circuitpython import from_config
        adapter = from_config(config)
    return InputManager(
        state, adapter or NullInputAdapter(),
        config.get("mpg_counts_per_detent", 4),
        config.get("mpg_direction", 1),
        config.get("button_debounce", 0.03),
        config.get("button_long_press", 0.8),
        config.get("axis_map"),
    )


def build_display(config):
    if config.get("display_enabled"):
        from src.display.displayio_backend import from_config
        return from_config(config)
    return ConsoleDisplay()


def build_storage(config):
    mount = None
    status = None
    error = None
    jobs_path = config.get("jobs_path", "/jobs")
    macros_path = config.get("macros_path", "/macros")
    config_path = "/config"
    if config.get("sd_enabled"):
        from src.storage.circuitpython_sd import mount_from_config
        mount, status, error = mount_from_config(config)
        root = config.get("sd_mount_path", "/sd").rstrip("/")
        jobs_path = root + "/jobs"
        macros_path = root + "/macros"
        config_path = root + "/config"
    storage = SDStorage(jobs_path, macros_path, config_path)
    if status is not None and status != "available":
        storage.status = status
        storage.error = error
    return storage, mount


def build_indicator(config):
    return indicator_from_config(config)
