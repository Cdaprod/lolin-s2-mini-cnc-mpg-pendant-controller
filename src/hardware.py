"""Central optional-hardware composition; unknown assignments stay disabled."""

from src.display.console import ConsoleDisplay
from src.display.indicator import from_config as indicator_from_config
from src.input.manager import InputManager, NullInputAdapter
from src.storage.sdcard import SDStorage


def scan_i2c(i2c):
    """Return detected 7-bit addresses without writing to any peripheral."""
    if i2c is None or not i2c.try_lock():
        return (), "I2C bus busy" if i2c is not None else None
    try:
        return tuple(sorted(int(address) for address in i2c.scan())), None
    except Exception as exc:
        return (), "I2C scan failed: {}".format(type(exc).__name__)
    finally:
        i2c.unlock()


def build_shared_i2c(config):
    """Construct the one configured CircuitPython I2C bus for all consumers."""
    sda_name = config.get("i2c_sda_pin")
    scl_name = config.get("i2c_scl_pin")
    if not sda_name or not scl_name:
        return None, None
    try:
        import board
        import busio
        return busio.I2C(getattr(board, scl_name), getattr(board, sda_name)), None
    except (ImportError, AttributeError, ValueError, RuntimeError) as exc:
        return None, "I2C initialization failed: {}".format(type(exc).__name__)


def build_inputs(config, state, shared_i2c=None):
    adapter = None
    if config.get("inputs_enabled"):
        from src.input.circuitpython import from_config
        adapter = from_config(config, shared_i2c=shared_i2c)
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
        if config.get("display_renderer") == "round":
            from src.display.round_ui.display import from_config
            return from_config(config)
        from src.display.displayio_backend import from_config
        return from_config(config)
    return ConsoleDisplay()


def build_storage(config, shared_spi=None):
    mount = None
    status = None
    error = None
    jobs_path = config.get("jobs_path", "/jobs")
    macros_path = config.get("macros_path", "/macros")
    config_path = "/config"
    if config.get("sd_enabled"):
        from src.storage.circuitpython_sd import mount_from_config
        mount, status, error = mount_from_config(config, shared_spi)
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
