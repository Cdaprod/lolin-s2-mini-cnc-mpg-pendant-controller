# UGS WiFi Pendant reference notes

Reference:

- `aleslukek/UGS-Wifi-Pendant`

The legacy project is useful for understanding the Universal Gcode Sender
Wi-Fi pendant workflow, but it is not the firmware base for this repository.

Reasons:

- it targets ESP8266 and Arduino
- this project targets ESP32-S2 and CircuitPython
- the original pendant combines input scanning, controller requests and
  display behavior tightly
- this project will isolate those layers

The reference implementation uses a UGS server port of `8080` and translates
button events into web requests to the UGS pendant interface.

It also documents a critical failure mode: Wi-Fi jogging can occasionally fail
to stop. Therefore this project will not implement jog motion until the input
state machine, stop semantics and watchdog behavior are defined.

Future UGS work belongs in a dedicated adapter such as:

```text
src/transports/ugs.py
```

rather than in `code.py`.
