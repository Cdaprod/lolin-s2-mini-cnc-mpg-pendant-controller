"""Allocation-free visual tokens for the round CNC instrument panel."""

BACKGROUND = 0x030708
PANEL = 0x101719
TEXT = 0xF4F7F8
MUTED = 0x738084
CYAN = 0x00D9EC
GREEN = 0x21E69A
YELLOW = 0xF2C230
RED = 0xFF4057

MACHINE_COLORS = {
    "idle": GREEN, "run": CYAN, "jog": CYAN, "hold": YELLOW,
    "alarm": RED, "estop": RED, "disconnected": MUTED,
}
