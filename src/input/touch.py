"""Normalize a touch controller into UI events; never dispatch machine actions."""

from src.display.ui import ROTATE_CCW, ROTATE_CW, TouchEvent


class TouchInput:
    """Recognize tap, long-press, and deliberate vertical page movement."""

    def __init__(self, source, clock, long_press=0.8, swipe_distance=45):
        self.source = source
        self.clock = clock
        self.long_press = float(long_press)
        self.swipe_distance = int(swipe_distance)
        self._start = None
        self._started_at = None

    def poll(self):
        point = self.source.point()
        now = self.clock()
        if point is not None and self._start is None:
            self._start = (int(point[0]), int(point[1]))
            self._started_at = now
            return ()
        if point is not None:
            return ()
        if self._start is None:
            return ()
        x, y = self._start
        end = self.source.last_point() or self._start
        duration = now - self._started_at
        self._start = None
        self._started_at = None
        delta_y = int(end[1]) - y
        if abs(delta_y) >= self.swipe_distance:
            return (ROTATE_CW if delta_y < 0 else ROTATE_CCW,)
        return (TouchEvent("long_press" if duration >= self.long_press else
                           "tap", x, y),)


class CST8XXTouchSource:
    """Small adapter around the CircuitPython CST816/CST8XX driver."""

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
    """Build the Seeed round-display touch source on the shared I2C bus."""
    import adafruit_cst8xx
    return CST8XXTouchSource(adafruit_cst8xx.CST8XX(i2c))
