"""Optional configured CircuitPython SPI SD mount; no default pins."""


class SDMount:
    def __init__(self, spi, card, mount_path):
        self.spi = spi
        self.card = card
        self.mount_path = mount_path
        self.mounted = True

    def deinit(self):
        if not self.mounted:
            return
        self.mounted = False
        try:
            import storage
            storage.umount(self.mount_path)
        finally:
            if hasattr(self.card, "deinit"):
                self.card.deinit()


def mount_from_config(config, spi=None):
    """Mount configured SD hardware or return `(None, status, error)`."""
    if not config.get("sd_enabled"):
        return None, "unconfigured", None
    names = (
        config.get("sd_sck_pin"), config.get("sd_mosi_pin"),
        config.get("sd_miso_pin"), config.get("sd_cs_pin"),
    )
    if not all(names):
        return None, "mount_error", "all SD SPI pin names are required"
    operation = "import SD support"
    card = None
    mount_path = config.get("sd_mount_path", "/sd")
    mounted = False
    owns_spi = spi is None
    try:
        import board
        import busio
        import sdcardio
        import storage
        if spi is None:
            operation = "allocate standalone SD SPI"
            spi = busio.SPI(getattr(board, names[0]),
                            MOSI=getattr(board, names[1]),
                            MISO=getattr(board, names[2]))
        operation = "initialize SD card (check card, CS, and shared SPI wiring)"
        card = sdcardio.SDCard(spi, getattr(board, names[3]))
        operation = "mount FAT filesystem at {}".format(mount_path)
        storage.mount(storage.VfsFat(card), mount_path)
        mounted = True
        # Create the optional data directories, but never report a writable
        # card as healthy when jobs cannot be read or initialized.
        import os
        jobs_path = mount_path.rstrip("/") + "/jobs"
        for folder in ("jobs", "macros", "config", "fonts", "logs"):
            path = mount_path.rstrip("/") + "/" + folder
            try:
                os.mkdir(path)
            except OSError:
                pass  # Existing folders or read-only media are acceptable.
        operation = "read SD jobs directory"
        os.listdir(jobs_path)
        return SDMount(spi, card, mount_path), "available", None
    except Exception as exc:
        # SD is optional: a mount failure must never stop display/UI boot.
        if mounted:
            try:
                storage.umount(mount_path)
            except (AttributeError, OSError, RuntimeError):
                pass
        if card is not None and hasattr(card, "deinit"):
            try:
                card.deinit()
            except (OSError, RuntimeError):
                pass
        if owns_spi and spi is not None and hasattr(spi, "deinit"):
            try:
                spi.deinit()
            except (OSError, RuntimeError):
                pass
        detail = "{}: {}".format(type(exc).__name__, str(exc)[:80])
        return None, "mount_error", "{}: {}".format(operation, detail)
