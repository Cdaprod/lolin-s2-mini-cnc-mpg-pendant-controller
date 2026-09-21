"""CircuitPython UART transport; hardware imports occur only on construction."""

from .base import Transport


class UARTTransport(Transport):
    name = "uart"

    def __init__(self, uart):
        self.uart = uart
        self._buffer = bytearray()
        self._connected = True

    @classmethod
    def from_pin_names(cls, tx_name, rx_name, baudrate=115200):
        if not tx_name or not rx_name:
            raise ValueError("MPG_UART_TX_PIN and MPG_UART_RX_PIN are required")
        import board
        import busio
        tx = getattr(board, tx_name)
        rx = getattr(board, rx_name)
        # CircuitPython UART defaults are 8 data bits, no parity, one stop bit.
        return cls(busio.UART(tx, rx, baudrate=int(baudrate), timeout=0))

    @property
    def connected(self):
        return self._connected

    def write(self, data):
        return self.uart.write(data)

    def readline(self):
        while self.uart.in_waiting:
            chunk = self.uart.read(min(self.uart.in_waiting, 64))
            if chunk:
                self._buffer.extend(chunk)
            newline = self._buffer.find(b"\n")
            if newline >= 0:
                line = bytes(self._buffer[:newline + 1])
                del self._buffer[:newline + 1]
                return line
        return None

    def close(self):
        self._connected = False
        self.uart.deinit()
