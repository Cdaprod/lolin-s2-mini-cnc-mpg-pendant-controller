# MASTER HARDWARE PINOUT

Cdaprod CNC MPG Pendant
Target: Seeed Studio XIAO ESP32-S3 + Round Display + MCP23017

This document is the canonical physical wiring reference for the current
pendant hardware.

IMPORTANT:
“Allocated” means that a logical connection has been assigned.
It does NOT mean that an unverified electrical interface is safe to connect.

===============================================================================
SYSTEM ARCHITECTURE
===============================================================================

DEVICE / CIRCUIT                 PURPOSE
-——————————————————————————
XIAO ESP32-S3                    Main MCU
Seeed Round Display for XIAO     240x240 display / touch / RTC / microSD
Waveshare MCP23017               Slow control GPIO expansion
LM393                            Prototype MPG differential interface
MPG handwheel                    A/A- and B/B- incremental encoder
Original selector switches       Axis and multiplier selection
Original momentary button        Local SELECT / ACCEPT input
Original mushroom switch         Remote stop input


===============================================================================
IMPORTANT — TWO DIFFERENT WIRING LAYERS
===============================================================================

The original pendant reuses some wire colors internally.

There are TWO different sets of wires being discussed:

1. MAIN PENDANT CABLE

   These are the manufacturer-defined conductors in the main multi-conductor
   pendant cable.

2. LOCAL INTERNAL WIRING

   These are short wires running between the original pendant PCB and the
   physical controls.

The same colors can therefore have different functions depending on which
wiring layer is being discussed.


MAIN CABLE:

Pink/Black       = Axis 6
Orange/Black     = Multiplier selector COM


LOCAL PCB -> MOMENTARY BUTTON:

Pink/Black       = One momentary-button contact
Orange/Black     = Other momentary-button contact


Therefore:

MAIN Pink/Black is NOT the same conductor as LOCAL Pink/Black.

MAIN Orange/Black is NOT the same conductor as LOCAL Orange/Black.

Never identify these wires by color without also identifying whether the
wire belongs to the MAIN CABLE or LOCAL INTERNAL wiring.


===============================================================================
MAIN PENDANT CABLE — MANUFACTURER WIRING MAP
===============================================================================

WIRE             SIGNAL       FUNCTION
-——————————————————————————
Red              VCC          MPG encoder supply
Black            0V           MPG encoder ground

Green            A            Encoder A phase
Violet           A-           Differential/inverted A

White            B            Encoder B phase
Violet/Black     B-           Differential/inverted B

Yellow           X            X-axis selector
Yellow/Black     Y            Y-axis selector
Brown            Z            Z-axis selector
Brown/Black      4            4th / A-axis selector
Pink             5            Axis 5 / B
Pink/Black       6            Axis 6 / C

Gray             X1           x1 multiplier selector
Gray/Black       X10          x10 multiplier selector
Orange           X100         x100 multiplier selector
Orange/Black     COM          Multiplier selector common

Blue             C            E-stop contact
Blue/Black       NC/CN        E-stop NC/contact

Green/Black      LED+         Original pendant indicator LED +
White/Black      LED-         Original pendant indicator LED -

Shield           Shield       Main cable shield


===============================================================================
MPG HANDWHEEL ENCODER
===============================================================================

The handwheel provides complementary/differential quadrature signals:

A / A-
B / B-

The encoder does NOT connect through the MCP23017.

The encoder gets dedicated native ESP32-S3 GPIO inputs because the handwheel
is the high-speed input device.


WIRE             SIGNAL       CONNECT TO
-——————————————————————————
Green            A            LM393 pin 3  IN1+
Violet           A-           LM393 pin 2  IN1-

White            B            LM393 pin 5  IN2+
Violet/Black     B-           LM393 pin 6  IN2-

Black            0V           Common logic GND
Red              VCC          Encoder supply — VOLTAGE NOT YET VERIFIED


LM393 OUTPUT SIDE:

LM393 pin 1      Encoder A     XIAO GPIO42 / MTMS
LM393 pin 7      Encoder B     XIAO GPIO41 / MTDI
LM393 pin 4      Ground        Common logic GND
LM393 pin 8      VCC           SUPPLY NOT YET VERIFIED


LM393 OUTPUT PULL-UPS:

XIAO 3V3
   |
  4.7k
   |
   +-————— LM393 pin 1
   |
   +-————— XIAO GPIO42 / MTMS


XIAO 3V3
   |
  4.7k
   |
   +-————— LM393 pin 7
   |
   +-————— XIAO GPIO41 / MTDI


IMPORTANT:

The two 4.7k resistors are independent pull-ups.

Do NOT connect LM393 pin 1 and pin 7 together.

Do NOT place the 4.7k resistors in series between the LM393 and ESP32.

The LM393 outputs are open collector. Each output node is pulled HIGH to
3.3V independently.


===============================================================================
ENCODER GPIO ASSIGNMENT
===============================================================================

SIGNAL           XIAO ESP32-S3
-——————————————————————————
MPG A            GPIO42 / MTMS
MPG B            GPIO41 / MTDI


GPIO42 and GPIO41 are underside XIAO pads.

GPIO42 = MTMS
GPIO41 = MTDI

They are deliberately being repurposed as normal GPIO for the MPG.

External JTAG using these pads cannot be used simultaneously with this
assignment.

Normal USB-C flashing/serial operation is separate.


===============================================================================
ENCODER ELECTRICAL VERIFICATION STILL REQUIRED
===============================================================================

The logical GPIO allocation is complete.

The following electrical characteristics are NOT yet considered verified:

1. Encoder Red/VCC required supply voltage.
2. Encoder A/A-/B/B- HIGH and LOW voltages.
3. Encoder output topology.
4. LM393 supply voltage.
5. LM393 input compatibility with measured encoder signals.
6. Encoder direction.
7. Actual counts-per-detent behavior.

Do not treat the encoder interface as electrically commissioned merely
because GPIO41/GPIO42 have been allocated.

A purpose-built differential receiver may eventually replace the LM393
prototype without changing the GPIO41/GPIO42 assignment.


===============================================================================
MCP23017
===============================================================================

The MCP23017 handles SLOW pendant controls:

- Axis selector
- Multiplier selector
- Momentary button
- Remote E-stop observation
- Future buttons / deadman input

The MPG handwheel itself does NOT pass through the MCP23017.


CONNECTION       CONNECT TO
-——————————————————————————
VCC              XIAO 3V3
GND              XIAO GND
SDA              XIAO D4 / GPIO5
SCL              XIAO D5 / GPIO6


I2C ADDRESS:

0x20 hexadecimal
32 decimal


The MCP23017 shares the I2C bus with the Round Display’s I2C peripherals.


===============================================================================
MCP23017 BANK A — AXIS SELECTOR
===============================================================================

MAIN-CABLE
WIRE             SIGNAL       MCP23017
-——————————————————————————
Yellow           X            GPA0
Yellow/Black     Y            GPA1
Brown            Z            GPA2
Brown/Black      4            GPA3
Pink             5            GPA4
Pink/Black       6            GPA5


Firmware axis mapping:

X -> AXIS_X / Operational
Y -> AXIS_Y / Operational
Z -> AXIS_Z / Operational
4 -> FILES / Explorer
5 -> CONFIG / Configuration
6 -> PREVIEW / safe Test & Demo

The semantic map is configurable; a verified six-axis profile may map the same
GPA3/GPA4/GPA5 contacts to AXIS_A/AXIS_B/AXIS_C without changing wiring.


===============================================================================
MCP23017 — MULTIPLIER SELECTOR
===============================================================================

MAIN-CABLE
WIRE             SIGNAL       MCP23017
-——————————————————————————
Gray             x1           GPA6
Gray/Black       x10          GPA7
Orange           x100         GPB0
Orange/Black     COM          Common GND


Intended active-low topology:

                     MCP internal pull-up
                           |
                           |
GPA6 / GPA7 / GPB0 ———+
                           |
                     selector contact
                           |
                           |
MAIN Orange/Black COM ——+
                           |
                          GND


SELECTED:

Input = LOW


NOT SELECTED:

Input = HIGH


===============================================================================
LOCAL MOMENTARY BUTTON
===============================================================================

IMPORTANT:

These are LOCAL internal wires, NOT the identically colored main-cable
conductors.


LOCAL WIRE       FUNCTION                         CONNECT TO
-——————————————————————————
Orange/Black     Momentary button input           MCP23017 GPB2
Pink/Black       Momentary button common          Common GND


GPB2 uses a pull-up.

Button released:

GPB2 = HIGH


Button pressed:

GPB2 = LOW


Firmware function:

GPB2 = SELECT / ACCEPT


===============================================================================
REMOTE E-STOP INPUT
===============================================================================

MAIN-CABLE
WIRE             SIGNAL                           CONNECT TO
-——————————————————————————
Blue             E-stop contact                   MCP23017 GPB1
Blue/Black       E-stop contact return            Common GND


GPB1 uses a pull-up and is interpreted as an active-low input.

This is the pendant’s REMOTE STOP / E-STOP OBSERVATION input.

It is NOT being represented as the machine cabinet’s hardwired safety
E-stop circuit.

The cabinet’s actual machine safety chain remains a separate hardware
system.


===============================================================================
MCP23017 COMPLETE ALLOCATION
===============================================================================

PIN              FUNCTION                         WIRE / CONTROL
-——————————————————————————
GPA0             Axis X                           MAIN Yellow
GPA1             Axis Y                           MAIN Yellow/Black
GPA2             Axis Z                           MAIN Brown
GPA3             Axis 4 / A                       MAIN Brown/Black
GPA4             Axis 5 / B                       MAIN Pink
GPA5             Axis 6 / C                       MAIN Pink/Black
GPA6             Multiplier x1                    MAIN Gray
GPA7             Multiplier x10                   MAIN Gray/Black

GPB0             Multiplier x100                  MAIN Orange
GPB1             Remote E-stop observe            MAIN Blue
GPB2             SELECT / momentary               LOCAL Orange/Black
GPB3             Reserved — BACK                  Future
GPB4             Reserved — FN                    Future
GPB5             Reserved — CANCEL                Future
GPB6             Reserved — DEADMAN               Future
GPB7             Reserved                         Future expansion


COMMON / RETURN CONNECTIONS:

MAIN Orange/Black      Multiplier COM       -> GND
MAIN Blue/Black        E-stop return        -> GND
LOCAL Pink/Black       Momentary return     -> GND


===============================================================================
MCP23017 INTERRUPTS
===============================================================================

INTA and INTB are not required for the initial implementation.

The encoder bypasses the MCP23017 entirely.

Selectors, buttons and remote-stop observation are sufficiently slow to be
handled through the I2C input backend without allocating another XIAO GPIO
for MCP23017 interrupts.

INTA and INTB remain available for future use.


===============================================================================
XIAO ESP32-S3 + ROUND DISPLAY RESOURCE MAP
===============================================================================

XIAO PIN         ESP32-S3 GPIO     CURRENT FUNCTION
-——————————————————————————
D0               GPIO1             Round Display battery measurement
D1               GPIO2             LCD CS
D2               GPIO3             microSD CS
D3               GPIO4             LCD DC
D4               GPIO5             I2C SDA
D5               GPIO6             I2C SCL
D6               GPIO43            LCD backlight
D7               GPIO44            Touch interrupt
D8               GPIO7             SPI SCK
D9               GPIO8             SPI MISO
D10              GPIO9             SPI MOSI

MTMS             GPIO42            MPG encoder A
MTDI             GPIO41            MPG encoder B


===============================================================================
I2C BUS
===============================================================================

XIAO PIN         GPIO         FUNCTION
-——————————————————————————
D4               GPIO5        SDA
D5               GPIO6        SCL


Devices sharing this bus include:

- Round Display touch controller
- Round Display RTC
- MCP23017 GPIO expander


MCP23017 address:

0x20


===============================================================================
ROUND DISPLAY
===============================================================================

DEVICE:

Seeed Studio Round Display for XIAO
240 x 240
GC9A01A-class round LCD


FUNCTION         XIAO PIN       ESP32-S3 GPIO
-——————————————————————————
LCD CS           D1             GPIO2
LCD DC           D3             GPIO4
Backlight        D6             GPIO43

SPI SCK          D8             GPIO7
SPI MISO         D9             GPIO8
SPI MOSI         D10            GPIO9

Touch SDA        D4             GPIO5
Touch SCL        D5             GPIO6
Touch INT        D7             GPIO44

Battery sense    D0             GPIO1


Display dimensions:

Width            240
Height           240


===============================================================================
MICROSD
===============================================================================

The Round Display’s microSD interface shares the SPI bus with the display.


FUNCTION         XIAO PIN       ESP32-S3 GPIO
-——————————————————————————
SCK              D8             GPIO7
MOSI             D10            GPIO9
MISO             D9             GPIO8
SD CS            D2             GPIO3


Mount target:

/sd


===============================================================================
SHARED SPI BUS
===============================================================================

FUNCTION         XIAO PIN       GPIO
-——————————————————————————
SCK              D8             GPIO7
MOSI             D10            GPIO9
MISO             D9             GPIO8


Individual chip selects:

LCD CS           D1             GPIO2
SD CS            D2             GPIO3


===============================================================================
ORIGINAL PENDANT INDICATOR LED
===============================================================================

MAIN-CABLE
WIRE             SIGNAL       CONNECTION
-——————————————————————————
Green/Black      LED+         UNASSIGNED
White/Black      LED-         UNASSIGNED


The original pendant LED electrical characteristics have NOT yet been
verified.

Before assigning an output:

1. Determine LED operating voltage.
2. Determine current requirement.
3. Determine whether an existing series resistor/driver is present.
4. Determine whether an external transistor/MOSFET driver is required.

Do NOT connect the original LED directly to a XIAO or MCP23017 output until
these measurements are complete.


===============================================================================
COMMON LOGIC GROUND
===============================================================================

The current pendant logic common includes:

XIAO GND
MCP23017 GND
LM393 pin 4
Encoder Black / 0V
MAIN Orange/Black multiplier COM
MAIN Blue/Black remote-stop return
LOCAL Pink/Black momentary-button return


These are signal/common connections.

They are NOT the cable shield.


===============================================================================
CABLE SHIELD
===============================================================================

MAIN cable shield remains separate from logic GND in the pendant wiring
definition.

Do not automatically connect:

Shield -> XIAO GND

The final shield termination belongs to the machine/enclosure grounding and
EMI strategy.


===============================================================================
GRBL / DOESBOT INTERFACE
===============================================================================

No XIAO UART pins are permanently allocated yet.

The previous LOLIN S2 Mini document assigned GPIO17/GPIO18.

THOSE ASSIGNMENTS DO NOT APPLY TO THIS XIAO ESP32-S3 BUILD.


UART TX          UNASSIGNED
UART RX          UNASSIGNED


The Doesbot 8-pin/offline-controller electrical pinout remains unverified.

Do NOT connect XIAO GPIO directly to unknown Doesbot 8-pin signals until the
electrical pinout, voltage levels and signal directions have been verified.


===============================================================================
XIAO ESP32-S3 SUMMARY
===============================================================================

GPIO1      / D0       Round Display battery measurement
GPIO2      / D1       LCD CS
GPIO3      / D2       microSD CS
GPIO4      / D3       LCD DC

GPIO5      / D4       Shared I2C SDA
GPIO6      / D5       Shared I2C SCL

GPIO43     / D6       LCD backlight
GPIO44     / D7       Touch interrupt

GPIO7      / D8       Shared SPI SCK
GPIO8      / D9       Shared SPI MISO
GPIO9      / D10      Shared SPI MOSI

GPIO42     / MTMS     MPG encoder A after LM393
GPIO41     / MTDI     MPG encoder B after LM393


===============================================================================
MCP23017 SUMMARY
===============================================================================

GPA0      Axis X
GPA1      Axis Y
GPA2      Axis Z
GPA3      Axis 4 / A
GPA4      Axis 5 / B
GPA5      Axis 6 / C
GPA6      Multiplier x1
GPA7      Multiplier x10

GPB0      Multiplier x100
GPB1      Remote E-stop observe
GPB2      Existing momentary SELECT button
GPB3      Reserved BACK
GPB4      Reserved FN
GPB5      Reserved CANCEL
GPB6      Reserved DEADMAN
GPB7      Reserved expansion


===============================================================================
FIRMWARE PIN MAP
===============================================================================

MPG_PIN_A                  GPIO42
MPG_PIN_B                  GPIO41

MPG_PIN_AXIS_X             GPA0
MPG_PIN_AXIS_Y             GPA1
MPG_PIN_AXIS_Z             GPA2
MPG_PIN_AXIS_4             GPA3
MPG_PIN_AXIS_5             GPA4
MPG_PIN_AXIS_6             GPA5

MPG_PIN_MULTIPLIER_X1      GPA6
MPG_PIN_MULTIPLIER_X10     GPA7
MPG_PIN_MULTIPLIER_X100    GPB0

MPG_PIN_ESTOP_OBSERVE      GPB1
MPG_PIN_BUTTON_SELECT      GPB2

MPG_PIN_BUTTON_BACK        GPB3     RESERVED
MPG_PIN_BUTTON_FN          GPB4     RESERVED
MPG_PIN_BUTTON_CANCEL      GPB5     RESERVED
MPG_PIN_DEADMAN            GPB6     RESERVED

MPG_I2C_SDA_PIN            D4
MPG_I2C_SCL_PIN            D5
MPG_MCP23017_ADDRESS       32 / 0x20

MPG_SPI_SCK_PIN            D8
MPG_SPI_MOSI_PIN           D10
MPG_SPI_MISO_PIN           D9

MPG_DISPLAY_CS_PIN         D1
MPG_DISPLAY_DC_PIN         D3
MPG_DISPLAY_BACKLIGHT_PIN  D6

MPG_SD_CS_PIN              D2


===============================================================================
VERIFICATION STATUS
===============================================================================

LOGICAL ALLOCATION COMPLETE:

[ALLOCATED] MPG A -> GPIO42
[ALLOCATED] MPG B -> GPIO41

[ALLOCATED] Axis X -> GPA0
[ALLOCATED] Axis Y -> GPA1
[ALLOCATED] Axis Z -> GPA2
[ALLOCATED] Axis 4 -> GPA3
[ALLOCATED] Axis 5 -> GPA4
[ALLOCATED] Axis 6 -> GPA5

[ALLOCATED] x1   -> GPA6
[ALLOCATED] x10  -> GPA7
[ALLOCATED] x100 -> GPB0

[ALLOCATED] Remote E-stop -> GPB1
[ALLOCATED] Local momentary SELECT -> GPB2

[RESERVED] BACK -> GPB3
[RESERVED] FN -> GPB4
[RESERVED] CANCEL -> GPB5
[RESERVED] DEADMAN -> GPB6
[RESERVED] Expansion -> GPB7


ELECTRICAL VERIFICATION STILL REQUIRED:

[VERIFY] Encoder required VCC
[VERIFY] Encoder A/A-/B/B- voltage levels
[VERIFY] Encoder output topology
[VERIFY] LM393 supply/input compatibility
[VERIFY] Encoder direction
[VERIFY] Counts per detent

[VERIFY] Axis selector contact behavior
[VERIFY] Multiplier selector COM/contact behavior
[VERIFY] Remote E-stop NC/contact behavior
[VERIFY] Local momentary-button behavior

[VERIFY] Original pendant LED voltage/current
[VERIFY] Doesbot 8-pin electrical interface


===============================================================================
DO NOT DIRECT-WIRE UNTIL VERIFIED
===============================================================================

1. Encoder Red/VCC
   Required supply voltage has not yet been established.

2. Encoder A/A-/B/B-
   Use the planned receiver/interface. Do not assume raw encoder outputs are
   ESP32-safe.

3. LM393 VCC
   Final supply/input compatibility depends on measured encoder signals.

4. Pendant LED+/LED-
   Operating voltage/current remain unverified.

5. Doesbot 8-pin interface
   Electrical pinout and voltage levels remain unverified.

6. Cable shield
   Do not substitute the shield for logic GND.

7. Remote E-stop
   GPB1 is the pendant firmware’s remote-stop input. It does not replace the
   machine’s independent hardwired safety system.


===============================================================================
SOURCE OF TRUTH
===============================================================================

This document and settings.toml.example must remain synchronized.

If a physical pin assignment changes:

1. Update this MASTER HARDWARE PINOUT.
2. Update settings.toml.example.
3. Update the MCP23017/input backend if required.
4. Update tests.
5. Do not silently remap physical pins in firmware.

Electrical verification flags must NOT be changed merely because a logical
pin assignment has been documented.
