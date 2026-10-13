"""Controller-neutral machine telemetry exposed to the pendant."""

AXES = ("X", "Y", "Z", "A", "B", "C")


def _ascii_field(value):
    # Never allow serial replacement characters or delimiters to break a
    # STATUS frame or raise UnicodeEncodeError in the host event loop.
    return "".join(ch if 32 <= ord(ch) <= 126 and ch != "|" else "?"
                   for ch in str(value or ""))[:96]


class MachineState:
    """Bounded normalized snapshot independent of a controller vendor."""

    def __init__(self):
        self.mode = "disconnected"
        self.machine_position = dict((axis, None) for axis in AXES)
        self.work_position = dict((axis, None) for axis in AXES)
        self.feed_rate = 0.0
        self.spindle_speed = 0.0
        self.alarm = None
        self.connected = False
        self.telemetry_fresh = False

    def status_payload(self):
        """Encode a compact protocol STATUS payload without JSON dependencies."""
        fields = ["STATE", _ascii_field(self.mode),
                  "1" if self.connected else "0"]
        for axis in AXES:
            value = self.work_position[axis]
            fields.append("" if value is None else "{:.4f}".format(value))
        fields.extend(("{:.1f}".format(self.feed_rate),
                       "{:.1f}".format(self.spindle_speed),
                       _ascii_field(self.alarm),
                       "FRESH" if self.telemetry_fresh else "STALE"))
        return "|".join(fields).encode("ascii")
