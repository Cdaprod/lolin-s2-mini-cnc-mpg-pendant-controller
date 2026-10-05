# Universal CNC host bridge architecture

The host bridge is the Protocol v1 responder and motion-lease owner running on
the CNC computer. It separates pendant communication from controller-specific
integration:

`pendant → Protocol v1 → HostBridge → ControllerAdapter → CNC controller`

Telemetry returns through the inverse path as normalized `MachineState`. The
pendant display therefore reflects controller-reported position and mode rather
than assuming a requested move occurred.

`ControllerAdapter` defines polling, continuous-jog start/stop, semantic command,
and shutdown boundaries. `MockControllerAdapter` supports deterministic tests.
`GrblAdapter` parses GRBL/grblHAL status reports and translates generic commands
and jog cancellation. Future Mach, LinuxCNC, or application adapters can
implement the same contract without changing pendant firmware or Protocol v1.

Physical motion is disabled by default. The host bridge does not select ports,
assign MCU pins, enable Doesbot hardware, or bypass electrical verification.
The 300 ms Protocol v1 lease remains the software bound: valid renewals retain
authority, explicit stop cancels immediately, and missing renewals invoke the
adapter's controller-specific stop. This remains independent of the hardwired
E-stop and is not a functional-safety mechanism.
