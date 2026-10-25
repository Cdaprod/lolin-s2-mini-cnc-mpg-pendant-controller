"""Optional configured CircuitPython SPI SD mount; no default pins."""


class SDMount:
    def __init__(self, spi, card, mount_path):
        self.spi = spi
        self.card = card
        self.mount_path = mount_path
        self.mounted = True


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
    try:
        import board
        import busio
        import sdcardio
        import storage
        if spi is None:
            spi = busio.SPI(getattr(board, names[0]),
                            MOSI=getattr(board, names[1]),
                            MISO=getattr(board, names[2]))
        card = sdcardio.SDCard(spi, getattr(board, names[3]))
        mount_path = config.get("sd_mount_path", "/sd")
        storage.mount(storage.VfsFat(card), mount_path)
        # A newly formatted card has no project directories. Initialize only
        # the optional data folders; never put boot code or secrets on SD.
        import os
        for folder in ("jobs", "macros", "config", "fonts", "logs"):
            path = mount_path.rstrip("/") + "/" + folder
            try:
                os.mkdir(path)
            except OSError:
                # Existing folders and read-only cards are nonfatal.
                pass
        return SDMount(spi, card, mount_path), "available", None
    except Exception as exc:
        return None, "mount_error", type(exc).__name__
