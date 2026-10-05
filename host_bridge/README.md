# Cdaprod Pendant Host Bridge

This host-side service boundary terminates pendant Protocol v1, owns the
receiver-local motion lease, publishes normalized `MachineState` telemetry, and
routes semantic commands through a replaceable `ControllerAdapter`. Stock GRBL
never sees pendant frames directly.

The initial adapters are `MockControllerAdapter` for tests and `GrblAdapter`
for GRBL/grblHAL serial streams. `motion_enabled` defaults to `False`; this
change does not select a serial port, assign pins, or authorize physical motion.
Future Mach, LinuxCNC, or application adapters implement the same interface.

Embedding example:

```python
from host_bridge.bridge import HostBridge
from host_bridge.adapters import GrblAdapter

adapter = GrblAdapter(controller_serial_transport, motion_enabled=False)
bridge = HostBridge(pendant_usb_transport, adapter, time.monotonic)
while running:
    bridge.poll()
```

Run tests from the repository root:

```sh
pytest -q tests/test_host_bridge.py
```
