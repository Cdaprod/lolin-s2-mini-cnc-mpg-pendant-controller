"""Pure-Python touch geometry and event recognition for the 240px UI.

No controller commands originate in this module.  It deliberately has no
CircuitPython imports so touch behaviors are testable on a development host.
"""

class TouchGestures:
    def __init__(self, clock, long_press=0.75, swipe_distance=58,
                 movement_tolerance=16, size=240, release_delay=0.07,
                 cooldown=0.22, min_duration=0.05):
        self.clock = clock
        self.long_press = float(long_press)
        self.swipe_distance = int(swipe_distance)
        self.movement_tolerance = int(movement_tolerance)
        self.size = int(size)
        self.release_delay = float(release_delay)
        self.cooldown = float(cooldown)
        self.min_duration = float(min_duration)
        self.missing_since = None
        self.block_until = 0.0
        self.start = None
        self.last = None
        self.started = 0
        self.active = False
        self.last_preview = None
        self.axis_lock = None

    def poll(self, point):
        """Return zero or one ('tap'|'long_press'|'swipe_*', x, y).

        Inputs and outputs use physical display coordinates. Gesture events
        are emitted on RELEASE, avoiding actions while a finger is down.
        """
        now = self.clock()
        if point is not None:
            self.missing_since = None
            if self.start is None and now < self.block_until:
                return ()
            x, y = int(point[0]), int(point[1])
            if not (0 <= x < self.size and 0 <= y < self.size):
                return ()
            if self.start is None:
                self.start = (x, y)
                self.started = now
                self.active = True
                self.last_preview = None
                self.axis_lock = None
                self.seen_motion = False
                self.last = (x, y)
                return ()
            self.last = (x, y)
            dx, dy = x - self.start[0], y - self.start[1]
            if self.axis_lock is None and max(abs(dx), abs(dy)) > self.movement_tolerance:
                # Lock the gesture's intent once; horizontal travel must
                # never preview menu rows, even if the finger crosses them.
                self.axis_lock = ("horizontal" if abs(dx) > abs(dy)
                                  else "vertical")
            if self.axis_lock == "horizontal":
                return ()
            if self.axis_lock != "vertical" or abs(dy) < self.movement_tolerance:
                return ()
            row = (y - 58) // 22 if 58 <= y < 190 else None
            if row is not None and row != self.last_preview:
                self.last_preview = row
                return (("drag", x, y),)
            return ()
        if self.start is None:
            return ()
        if self.missing_since is None:
            self.missing_since = now
            return ()
        if now - self.missing_since < self.release_delay:
            return ()
        x0, y0 = self.start
        x1, y1 = self.last or self.start
        duration = self.missing_since - self.started
        self.start = None
        self.last = None
        self.active = False
        self.last_preview = None
        axis_lock = self.axis_lock
        self.axis_lock = None
        self.missing_since = None
        self.block_until = now + self.cooldown
        if duration < self.min_duration:
            return ()
        dx, dy = x1 - x0, y1 - y0
        if axis_lock == "horizontal" and abs(dx) >= self.swipe_distance and abs(dx) >= abs(dy) * 1.5:
            kind = "swipe_right" if dx > 0 else "swipe_left"
        elif axis_lock == "vertical" and abs(dy) >= self.swipe_distance and abs(dy) >= abs(dx) * 1.5:
            kind = "swipe_down" if dy > 0 else "swipe_up"
        elif axis_lock == "horizontal":
            return ()
        elif axis_lock == "vertical":
            return ()
        elif abs(dx) <= self.movement_tolerance and abs(dy) <= self.movement_tolerance:
            kind = ("release_select" if 58 <= y1 < 190 else
                    "long_press" if duration >= self.long_press else "tap")
        else:
            return ()
        return ((kind, x1 if kind == "release_select" else x0,
                 y1 if kind == "release_select" else y0),)
