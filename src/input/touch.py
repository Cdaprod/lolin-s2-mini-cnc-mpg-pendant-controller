"""Touch input adapters. User-interface only, never machine motion."""

from src.display.ui import TouchEvent
from src.input.touch_gestures import TouchGestures


class TouchInput:
    """Normalize releases to UI navigation, with a tiny visual touch signal."""

    def __init__(self, source, clock, long_press=0.8, swipe_distance=58,
                 rotation=0, invert_x=False, invert_y=False):
        self.source = source
        self.gestures = TouchGestures(clock, long_press, swipe_distance)
        self.rotation = int(rotation) % 360
        self.invert_x = bool(invert_x)
        self.invert_y = bool(invert_y)
        self.last_feedback = None
        self.feedback_until = 0
        self.clock = clock
        self.poll_count = 0
        self.sample_count = 0
        self.event_count = 0
        self.last_point = None
        self.last_error = None
        self.consecutive_errors = 0

    def deinit(self):
        if hasattr(self.source, "deinit"):
            self.source.deinit()

    def _transform(self, point):
        if point is None:
            return None
        x, y = int(point[0]), int(point[1])
        if self.rotation == 90:
            x, y = 239 - y, x
        elif self.rotation == 180:
            x, y = 239 - x, 239 - y
        elif self.rotation == 270:
            x, y = y, 239 - x
        if self.invert_x:
            x = 239 - x
        if self.invert_y:
            y = 239 - y
        return x, y

    def poll(self):
        self.poll_count += 1
        try:
            point = self._transform(self.source.point())
            self.last_error = None
            self.consecutive_errors = 0
        except (OSError, RuntimeError, ValueError) as exc:
            self.last_error = type(exc).__name__
            self.consecutive_errors += 1
            return ()
        self.last_point = point
        if point is not None:
            self.sample_count += 1
        events = self.gestures.poll(point)
        if not events:
            return ()
        kind, x, y = events[0]
        self.event_count += 1
        self.last_feedback = (x, y, kind)
        self.feedback_until = self.clock() + 0.20
        if kind == "drag":
            return (TouchEvent(kind, x, y),)
        if kind == "swipe_up":
            return (TouchEvent(kind, x, y),)
        if kind == "swipe_down":
            return (TouchEvent(kind, x, y),)
        return (TouchEvent(kind, x, y),)


class CST8XXTouchSource:
    """Adapter for Seeed's CST816/CST8XX family (shared I2C)."""

    def __init__(self, controller):
        self.controller = controller
        self._last = None

    def point(self):
        point = self.controller.touch_point if self.controller.touched else None
        if point is not None:
            self._last = (point[0], point[1])
        return self._last if point is not None else None

    def last_point(self):
        return self._last


def build_cst8xx(i2c):
    """Create a touch source; the shared I2C bus also hosts MCP23017."""
    import adafruit_cst8xx
    return CST8XXTouchSource(adafruit_cst8xx.CST8XX(i2c))


class CHSC6XTouchSource:
    """Seeed Round Display CHSC6X at I2C 0x2e, IRQ D7 active-low.

    Seeed's reference firmware reads five bytes directly; byte 0 is a
    pressed marker (1), while bytes 2 and 4 contain 8-bit X/Y positions.
    All transactions share the existing I2C object with the MCP23017.
    """

    ADDRESS = 0x2E

    def __init__(self, i2c, irq=None):
        self.i2c = i2c
        self.irq = irq
        self.buffer = bytearray(5)
        self.irq_idle_count = 0
        self.bus_busy_count = 0
        self.read_count = 0

    def point(self):
        if self.irq is not None and self.irq.value:
            self.irq_idle_count += 1
            return None
        if not self.i2c.try_lock():
            # No new touch sample while other shared-I2C clients are busy.
            self.bus_busy_count += 1
            return None
        try:
            self.i2c.readfrom_into(self.ADDRESS, self.buffer)
            self.read_count += 1
        finally:
            self.i2c.unlock()
        if self.buffer[0] != 1:
            return None
        x, y = self.buffer[2], self.buffer[4]
        return (x, y) if x < 240 and y < 240 else None

    def deinit(self):
        if self.irq is not None:
            self.irq.deinit()
            self.irq = None


def build_chsc6x(i2c, irq_pin="D7"):
    """Create CHSC6X reader for the Seeed XIAO round display."""
    irq = None
    if irq_pin:
        import board
        import digitalio
        irq = digitalio.DigitalInOut(getattr(board, irq_pin))
        irq.direction = digitalio.Direction.INPUT
        irq.pull = digitalio.Pull.UP
    return CHSC6XTouchSource(i2c, irq)
