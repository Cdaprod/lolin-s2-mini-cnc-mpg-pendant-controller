"""Pure-Python touch geometry and event recognition for the 240px UI.

No controller commands originate in this module.  It deliberately has no
CircuitPython imports so touch behaviors are testable on a development host.
"""

class TouchGestures:
    def __init__(self, clock, long_press=0.75, swipe_distance=38,
                 movement_tolerance=12, size=240):
        self.clock = clock
        self.long_press = float(long_press)
        self.swipe_distance = int(swipe_distance)
        self.movement_tolerance = int(movement_tolerance)
        self.size = int(size)
        self.start = None
        self.last = None
        self.started = 0
        self.active = False

    def poll(self, point):
        """Return zero or one ('tap'|'long_press'|'swipe_*', x, y).

        Inputs and outputs use physical display coordinates. Gesture events
        are emitted on RELEASE, avoiding actions while a finger is down.
        """
        now = self.clock()
        if point is not None:
            x, y = int(point[0]), int(point[1])
            if not (0 <= x < self.size and 0 <= y < self.size):
                return ()
            if self.start is None:
                self.start = (x, y)
                self.started = now
                self.active = True
            self.last = (x, y)
            return ()
        if self.start is None:
            return ()
        x0, y0 = self.start
        x1, y1 = self.last or self.start
        duration = now - self.started
        self.start = None
        self.last = None
        self.active = False
        dx, dy = x1 - x0, y1 - y0
        if abs(dx) >= self.swipe_distance or abs(dy) >= self.swipe_distance:
            if abs(dx) > abs(dy):
                kind = "swipe_right" if dx > 0 else "swipe_left"
            else:
                kind = "swipe_down" if dy > 0 else "swipe_up"
        elif abs(dx) <= self.movement_tolerance and abs(dy) <= self.movement_tolerance:
            kind = "long_press" if duration >= self.long_press else "tap"
        else:
            return ()
        return ((kind, x0, y0),)
