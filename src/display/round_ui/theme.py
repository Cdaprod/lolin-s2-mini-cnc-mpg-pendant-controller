"""Small, editable 240px round UI palettes. No machine logic belongs here.

Add a palette to THEMES and set MPG_UI_THEME in settings.toml to activate it.
The original symbols remain for compatibility with existing renderers.
"""

THEMES = {
    "industrial": {
        "background": 0x030708, "panel": 0x101719, "text": 0xF4F7F8,
        "muted": 0x738084, "accent": 0x00D9EC, "success": 0x21E69A,
        "warning": 0xF2C230, "danger": 0xFF4057, "highlight": 0x15333A, "separator": 0x2A373C, "focus_border": 0x86989E,
    },
    "ice": {
        "background": 0x01080F, "panel": 0x0A1926, "text": 0xF2FCFF,
        "muted": 0x7496A9, "accent": 0x43E8FF, "success": 0x62F5C0,
        "warning": 0xFFCA5C, "danger": 0xFF5368, "highlight": 0x143548, "separator": 0x2B4754, "focus_border": 0x8AA9B6,
    },
    "amber": {
        "background": 0x090704, "panel": 0x19140A, "text": 0xFFF7DC,
        "muted": 0xA29174, "accent": 0xFFB62B, "success": 0xBFE970,
        "warning": 0xF5CE4B, "danger": 0xFF5163, "highlight": 0x403017, "separator": 0x493B28, "focus_border": 0xB2A48B,
    },
    "spectrum": {
        "background": 0x03050B, "panel": 0x101526, "text": 0xF6F8FF,
        "muted": 0x8C93AD, "accent": 0x00D8FF, "success": 0x65FBA9,
        "warning": 0xF6CC45, "danger": 0xFF4D72, "highlight": 0x29234A, "separator": 0x343448, "focus_border": 0x9498B3,
    },
}

# The physical page selector is authoritative. The four page colors are
# navigational identity only; warnings and alarms keep safety semantics.
PAGE_THEMES = {
    "HOME": "industrial",
    "OPERATIONAL": "industrial",
    "EXPLORER": "amber",
    "CONFIGURATION": "ice",
    "PREVIEW": "spectrum",
}


def for_page(page):
    """Resolve a physical top-level page to its visual palette."""
    return select(PAGE_THEMES.get(str(page or "HOME").upper(), "industrial"))


def shade_color(color, numerator, denominator=100):
    """Scale an RGB888 color for a compact antialiased HUD sprite."""
    red = ((color >> 16) & 0xFF) * numerator // denominator
    green = ((color >> 8) & 0xFF) * numerator // denominator
    blue = (color & 0xFF) * numerator // denominator
    return (red << 16) | (green << 8) | blue


def select(name):
    """Return immutable-by-convention palette mapping, falling back safely."""
    return THEMES.get(str(name or "industrial").lower(), THEMES["industrial"])


BACKGROUND = THEMES["industrial"]["background"]
PANEL = THEMES["industrial"]["panel"]
TEXT = THEMES["industrial"]["text"]
MUTED = THEMES["industrial"]["muted"]
CYAN = THEMES["industrial"]["accent"]
GREEN = THEMES["industrial"]["success"]
YELLOW = THEMES["industrial"]["warning"]
RED = THEMES["industrial"]["danger"]

MACHINE_COLORS = {
    "idle": GREEN, "run": CYAN, "jog": CYAN, "hold": YELLOW,
    "alarm": RED, "estop": RED, "disconnected": MUTED,
}
