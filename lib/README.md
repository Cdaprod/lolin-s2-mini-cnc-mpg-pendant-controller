# CircuitPython libraries

The network bootstrap uses only built-in `wifi`, `socketpool`, and `mdns`
modules provided by CircuitPython.

`requirements-circuitpython.txt` is the dependency inventory. Install it with:

```bash
circup --path /path/to/CIRCUITPY install -r requirements-circuitpython.txt
```

Alternatively vendor the corresponding `.mpy`, `.py`, or package under `lib/`.
The deployment tool copies actual library modules and validates selected-profile
imports. The Seeed round profile requires `adafruit_gc9a01a`.
