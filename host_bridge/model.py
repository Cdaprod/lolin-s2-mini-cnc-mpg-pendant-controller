"""Controller-neutral machine telemetry exposed to the pendant."""

AXES = ("X", "Y", "Z", "A", "B", "C")


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

    def status_payload(self):
        """Encode a compact protocol STATUS payload without JSON dependencies."""
        fields = ["STATE", self.mode, "1" if self.connected else "0"]
        for axis in AXES:
            value = self.work_position[axis]
            fields.append("" if value is None else "{:.4f}".format(value))
        fields.extend(("{:.1f}".format(self.feed_rate),
                       "{:.1f}".format(self.spindle_speed),
                       self.alarm or ""))
        return "|".join(fields).encode("ascii")
