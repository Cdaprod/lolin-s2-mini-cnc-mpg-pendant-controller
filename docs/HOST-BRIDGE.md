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

## GRBL motion admission and telemetry

`motion_enabled` remains `False` by default. HOME and RESUME are rejected while
it is false; HOLD, RESET, and jog cancellation remain available because they
remove or inhibit motion. The GRBL adapter additionally requires a connected
transport and a fresh controller mode of `Idle` or `Jog` before admitting a jog.

One accepted `MOTION_START` may write one segment, limited to 0.5 mm and 180 ms
of commanded travel. Each authenticated, in-order `MOTION_RENEW` may admit at
most one more segment. The adapter permits only one unacknowledged `$J=` command
and does not treat `ok` as completion: a later status report must confirm
`Idle` before another segment is admitted. Renewals received while a bounded
ACK/completion wait is in progress extend the receiver lease without queuing
work; missing ACK or completion confirmation fails closed after its deadline.
`error`, `ALARM`, an
unsuitable reported mode, serial disconnection, write failure, STOP, lease
expiry, session loss, or host shutdown clears the intent and requests realtime
jog cancel (`0x85`) when the connection can accept it. Duplicate protocol
renewals never reach the adapter. Reconnection never recreates an intent.

The host requests `?` status at a bounded 200 ms interval only while the serial
transport is connected. Telemetry older than one second is marked `STALE` in
the normalized status payload; a validated report changes it to `FRESH`.
Complete `WPos` is accepted directly; otherwise work position is derived only
when compatible `MPos` and `WCO` occur in the same validated status report.
Malformed/non-finite coordinate or feed fields do not partially mutate state.

These bounds limit host-side admission; they cannot retract bytes already
accepted into controller firmware or guarantee how quickly a particular GRBL
build decelerates after `0x85`. A killed host cannot transmit cancellation.
Short segments limit residual queued travel, but the machine's hardwired
E-stop/contactors remain the authoritative independent stop mechanism. Bench
validation must measure controller acknowledgement, planner buffering,
deceleration, disconnect, and process-termination behavior before motion is
enabled.
