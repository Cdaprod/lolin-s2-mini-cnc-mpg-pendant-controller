"""Minimal MCP23017 input bank for dry-contact selectors over shared I2C."""

IODIRA = 0x00
IODIRB = 0x01
GPPUA = 0x0C
GPPUB = 0x0D
GPIOA = 0x12


class MCP23017Pin:
    def __init__(self, bank, bit):
        self.bank = bank
        self.bit = int(bit)

    @property
    def value(self):
        return bool(self.bank.value & (1 << self.bit))


class MCP23017InputBank:
    """Cache a 16-bit input snapshot so one application poll uses one I2C read."""

    def __init__(self, i2c, address=0x20, pullup_mask=0x01FF):
        if not 0x20 <= int(address) <= 0x27:
            raise ValueError("MCP23017 address must be between 0x20 and 0x27")
        self.i2c = i2c
        self.address = int(address)
        self.value = 0xFFFF
        self.read_errors = 0
        self._write_pair(IODIRA, 0xFFFF)
        self._write_pair(GPPUA, int(pullup_mask) & 0xFFFF)

    def _lock(self):
        if not self.i2c.try_lock():
            raise RuntimeError("I2C bus busy during MCP23017 setup")

    def _write_pair(self, register, value):
        self._lock()
        try:
            self.i2c.writeto(
                self.address,
                bytes((register, value & 0xFF, (value >> 8) & 0xFF)),
            )
        finally:
            self.i2c.unlock()

    def pin(self, bit):
        if not 0 <= int(bit) <= 15:
            raise ValueError("MCP23017 bit must be 0..15")
        return MCP23017Pin(self, bit)

    def refresh(self):
        if not self.i2c.try_lock():
            self.read_errors += 1
            return False
        data = bytearray(2)
        try:
            self.i2c.writeto_then_readfrom(
                self.address, bytes((GPIOA,)), data
            )
            self.value = data[0] | (data[1] << 8)
            return True
        except OSError:
            self.read_errors += 1
            return False
        finally:
            self.i2c.unlock()
