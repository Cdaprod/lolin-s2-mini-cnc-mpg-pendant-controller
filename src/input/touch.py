"""CST8XX touch input. User-interface only, never machine motion."""

from src.display.ui import ROTATE_CCW, ROTATE_CW, TouchEvent
from src.input.touch_gestures import TouchGestures


class TouchInput:
    """Normalize releases to UI navigation, with a tiny visual touch signal."""

    def __init__(self, source, clock, long_press=0.8, swipe_distance=38,
                 rotation=0, invert_x=False, invert_y=False):
        self.source = source
        self.gestures = TouchGestures(clock, long_press, swipe_distance)
        self.rotation = int(rotation) % 360
        self.invert_x = bool(invert_x)
        self.invert_y = bool(invert_y)
        self.last_feedback = None
        self.feedback_until = 0
        self.clock = clock
        self.sample_count = 0
        self.event_count = 0

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
        point = self._transform(self.source.point())
        if point is not None:
            self.sample_count += 1
        events = self.gestures.poll(point)
        if not events:
            return ()
        kind, x, y = events[0]
        self.event_count += 1
        self.last_feedback = (x, y, kind)
        self.feedback_until = self.clock() + 0.20
        if kind == "swipe_up":
            return (ROTATE_CW,)
        if kind == "swipe_down":
            return (ROTATE_CCW,)
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
