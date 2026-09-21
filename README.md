# LOLIN S2 Mini CNC MPG Pendant Controller

CircuitPython firmware scaffold for a Wi-Fi connected CNC MPG/pendant built around the **LOLIN S2 Mini (ESP32-S2)**.

The initial milestone is deliberately small and safe:

- boot CircuitPython
- set a deterministic network hostname
- connect to Wi-Fi from `settings.toml`
- expose network/controller status through the serial console
- keep the existing `patterns.py` concept available
- isolate future CNC transports (UGS / ESP3D / direct GRBL) behind a controller module
- **do not send motion commands by default**

## Repository

`Cdaprod/lolin-s2-mini-cnc-mpg-pendant-controller`

## CIRCUITPY layout

Copy these files/folders to the root of the `CIRCUITPY` drive:

```text
CIRCUITPY/
├── code.py
├── patterns.py
├── settings.toml
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── network.py
│   └── controller.py
└── lib/
```

## 1. Configure Wi-Fi

Copy:

```text
settings.toml.example
```

to:

```text
settings.toml
```

Then edit the values.

Example:

```toml
CIRCUITPY_WIFI_SSID="cda_Lab"
CIRCUITPY_WIFI_PASSWORD="CHANGE_ME"

MPG_HOSTNAME="cda-lolin-s2-mpg"
MPG_CONTROLLER_MODE="disabled"
MPG_CONTROLLER_HOST=""
MPG_CONTROLLER_PORT="8080"
```

Do **not** commit `settings.toml`.

## 2. Boot behavior

On startup the board will:

1. read configuration
2. set `wifi.radio.hostname`
3. connect to Wi-Fi
4. print DHCP/network information
5. initialize the selected CNC controller transport
6. remain idle

Expected output:

```text
[boot] LOLIN S2 Mini CNC MPG Pendant
[net] hostname: cda-lolin-s2-mpg
[net] connecting to: cda_Lab
[net] connected
[net] ip: 192.168.0.x
[controller] mode: disabled
[ready] pendant runtime started
```

## Controller modes

### `disabled`

Default. Networking works, but CNC commands cannot be transmitted.

### `ugs`

Reserved for Universal Gcode Sender's Wi-Fi pendant HTTP interface.

The older `aleslukek/UGS-Wifi-Pendant` project is useful as a reference for the UGS pendant behavior, but it is ESP8266/Arduino firmware and is not copied into this CircuitPython project.

### `esp3d`

Reserved for the ESP3D/GRBL network bridge you are building.

### `grbl`

Reserved for a future direct GRBL serial/network transport.

## Safety architecture

Physical inputs should never call HTTP/socket functions directly.

Use this flow:

```text
buttons / encoder / selector
            │
            ▼
       input state
            │
            ▼
     pendant actions
            │
            ▼
   controller interface
      │            │
      ├─ UGS       │
      ├─ ESP3D     │
      └─ GRBL      │
            │
            ▼
       CNC machine
```

That lets us add:

- debounce
- press/release semantics
- jog watchdogs
- machine-state interlocks
- dead-man behavior
- reconnect handling
- explicit stop/cancel behavior

before the actual transport is allowed to move the machine.

## Development

A convenience deployment script is included:

```bash
./deploy.sh
```

It defaults to `/Volumes/CIRCUITPY`.

Override it with:

```bash
CIRCUITPY=/path/to/CIRCUITPY ./deploy.sh
```

## Next milestone

The next implementation should map the actual MPG hardware:

- axis selector
- increment selector
- encoder A/B
- enable/dead-man input
- cycle start
- feed hold
- reset
- home
- probe
- display/OLED if used

Then connect those actions to either ESP3D or UGS through `src/controller.py`.
