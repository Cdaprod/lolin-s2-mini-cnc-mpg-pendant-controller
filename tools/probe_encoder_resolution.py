
# CNC MPG / 100-DIVISION DIAL TEST v4
# LOLIN ESP32-S2 Mini / CircuitPython
# Encoder: A=GPIO1, B=GPIO2
# SSD1306: 128x32, I2C address 0x3C
#
# Hardware-backed quadrature capture using rotaryio.
# One full needle revolution = 100 logical positions.
# Raw counts are retained for encoder calibration.
#
# Machine motion is NOT enabled by this test.

import time
import math
import board
import rotaryio
import adafruit_ssd1306

# -------- SETTINGS --------
PIN_A = 1
PIN_B = 2

ADDRESS = 0x3C
WIDTH = 128
HEIGHT = 32

# Provisional: verify using physical dial.
COUNTS_PER_DIVISION = 4

# Change to -1 if direction is reversed.
DIRECTION = 1

DRAW_INTERVAL = 0.10
REPORT_INTERVAL = 1.0

# Needle dial: 25px diameter
CX = 15
CY = 15
RADIUS = 13


def gpio(number):
    for name in ("IO" + str(number),
                 "D" + str(number)):
        if hasattr(board, name):
            return getattr(board, name)

    raise RuntimeError(
        "GPIO{} unavailable".format(number)
    )


def show_failure(error):
    print("MPG ERROR:", repr(error))
    try:
        oled.fill(0)
        oled.text("MPG INIT FAILED", 0, 0, 1)
        oled.text(str(error)[:21], 0, 10, 1)
        oled.text("SEE USB CONSOLE", 0, 21, 1)
        oled.show()
    except Exception:
        pass

    while True:
        time.sleep(1)


print("\nMPG 100-DIVISION DIAL TEST v4")
print("A=GPIO{}, B=GPIO{}".format(PIN_A, PIN_B))

# -------- OLED --------
i2c = board.I2C()

while not i2c.try_lock():
    time.sleep(0.01)

try:
    devices = i2c.scan()
finally:
    i2c.unlock()

print("I2C:", [hex(x) for x in devices])

if ADDRESS not in devices:
    raise RuntimeError(
        "SSD1306 not found at 0x3C"
    )

oled = adafruit_ssd1306.SSD1306_I2C(
    WIDTH, HEIGHT, i2c, addr=ADDRESS
)

oled.fill(0)
oled.text("MPG DIAL TEST v4", 0, 0, 1)
oled.text("Initializing...", 0, 12, 1)
oled.show()

# -------- HARDWARE ENCODER --------
try:
    encoder = rotaryio.IncrementalEncoder(
        gpio(PIN_A),
        gpio(PIN_B),
        divisor=1
    )
except Exception as error:
    show_failure(error)

# Zero relative to the current physical position.
raw_zero = encoder.position
raw_position = 0
logical_position = 0
previous_raw = 0

direction_text = "."
last_draw = time.monotonic()
last_report = last_draw

print("READY")
print("Raw zero:", raw_zero)
print("Counts/division:", COUNTS_PER_DIVISION)
print("Turn exactly one full revolution.")
print("Check RAW change against expected 400.")

# -------- DISPLAY --------
def draw_dial(position):
    # Circular outline.
    oled.circle(CX, CY, RADIUS, 1)

    # Cardinal reference marks.
    oled.pixel(CX, CY - RADIUS, 1)
    oled.pixel(CX + RADIUS, CY, 1)
    oled.pixel(CX, CY + RADIUS, 1)
    oled.pixel(CX - RADIUS, CY, 1)

    # 100 positions = 360 degrees.
    dial_position = position % 100
    angle = dial_position * 2.0 * math.pi / 100.0

    x = CX + int(round(
        math.sin(angle) * (RADIUS - 3)
    ))
    y = CY - int(round(
        math.cos(angle) * (RADIUS - 3)
    ))

    oled.line(CX, CY, x, y, 1)
    oled.fill_rect(CX - 1, CY - 1, 3, 3, 1)


def render(raw, position, direction):
    oled.fill(0)

    draw_dial(position)

    # Signed logical position.
    oled.text(
        "P:{:+7d}".format(position),
        34, 0, 1
    )

    # Raw hardware quadrature count.
    oled.text(
        "R:{:+7d}".format(raw),
        34, 11, 1
    )

    # Needle phase and direction.
    oled.text(
        "{:02d}/100 {}".format(
            position % 100,
            direction
        ),
        34, 22, 1
    )

    oled.show()


# -------- MAIN LOOP --------
while True:
    now = time.monotonic()

    # Hardware-backed position reading.
    raw_position = (
        encoder.position - raw_zero
    ) * DIRECTION

    if raw_position > previous_raw:
        direction_text = "+"
    elif raw_position < previous_raw:
        direction_text = "-"

    previous_raw = raw_position

    # Truncate toward zero, keeping the initial
    # calibration symmetric for both directions.
    if raw_position >= 0:
        logical_position = (
            raw_position // COUNTS_PER_DIVISION
        )
    else:
        logical_position = -(
            (-raw_position) // COUNTS_PER_DIVISION
        )

    if now - last_draw >= DRAW_INTERVAL:
        last_draw = now
        render(
            raw_position,
            logical_position,
            direction_text
        )

    if now - last_report >= REPORT_INTERVAL:
        last_report = now

        print(
            "RAW={:+d} POS={:+d} "
            "DIAL={:02d}/100 DIR={}".format(
                raw_position,
                logical_position,
                logical_position % 100,
                direction_text
            )
        )
