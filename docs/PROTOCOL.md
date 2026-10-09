# Reliable pendant protocol v1

## Scope and architecture

The stack is `semantic command → ReliableSession → Transport`; receive order is
`Transport → FrameParser → CRC/version validation → session validation →
sequence validation → motion lease validation → semantic handler`.
`src.transport.base` is the replaceable byte-stream contract and its UART and
mock implementations contain no protocol semantics. `src.transport.protocol`
owns framing, handshake, reliability, link health, and motion leases. A
companion/controller adapter owns translation to GRBL or grblHAL; stock GRBL is
not expected to parse these frames. No UART or Doesbot pin is assigned or
enabled by this protocol.

`PendantState.link_state` and `link_diagnostics` expose renderer-independent
status. The firmware-observed remote-stop contact and the machine's hardwired
E-stop/contactors remain independent and authoritative. This protocol provides
software communication integrity and bounded software motion authorization; it
is not a functional-safety system or an E-stop replacement.

## Frame encoding

All multibyte integers are unsigned and big-endian.

| Field | Bytes | Meaning |
|---|---:|---|
| SOF | 1 | `0xA5` |
| protocol version | 1 | `1` |
| packet type | 1 | see below |
| source session | 8 | sender's nonzero incarnation/handshake nonce |
| peer session | 8 | expected peer nonce; zero only for SESSION_INIT |
| sequence | 2 | reliable serial number, modulo 65536 |
| message class | 1 | SAFETY=1, MOTION=2, COMMAND=3, STATUS=4, CONFIG=5, FILE=6 |
| flags | 1 | RELIABLE=`0x01`; MOTION_START=`0x02`; MOTION_RENEW=`0x04`; MOTION_STOP=`0x08` |
| payload length | 2 | 0 through 256 |
| payload | 0..256 | endpoint-defined bytes |
| CRC | 2 | CRC-16/CCITT-FALSE |
| EOF | 1 | `0x5A` |

Packet types are DATA=1, ACK=2, NAK=3, HEARTBEAT=4, CONTROL=5,
SESSION_INIT=6, SESSION_CHALLENGE=7, and SESSION_CONFIRM=8. The CRC covers every
byte from protocol version through the last payload byte. It uses polynomial
`0x1021`, initial value `0xFFFF`, no reflection, no final XOR. The maximum frame
is 284 bytes. The removed sender timestamp has no protocol-v1 replacement:
absolute monotonic time is never sent on the wire.

The parser rejects an oversized length as soon as the fixed header is present,
bounds retained storage to one maximum frame, validates version/type/EOF/CRC
before semantic dispatch, and searches corrupt data for the next SOF. CRC or
malformed DATA can produce a NAK only when its readable session pair matches
the active session. Garbage, truncation, concatenation, and a corrupt length
that swallows a later SOF do not require reboot.

## Session generation and handshake

Each endpoint contributes an independent 64-bit nonzero nonce. The default is
from `os.urandom(8)`; callers may inject a board-specific nonce factory. A nonce
is a practical stale-incarnation discriminator, not an authentication secret or
cryptographic identity. The roles are fixed per link: the pendant initiates and
the companion responds.

1. Initiator sends `SESSION_INIT(client_nonce, peer=0)`.
2. Responder records that proposal and sends
   `SESSION_CHALLENGE(server_nonce, peer=client_nonce)`.
3. Initiator validates its nonce, records the server nonce, sends
   `SESSION_CONFIRM(client_nonce, peer=server_nonce)`, and establishes.
4. Responder establishes only after a matching confirm.

The command identity is `(source_session, peer_session, sequence)`. DATA,
CONTROL, HEARTBEAT, ACK, and NAK are accepted only when both session fields
match the established pair in the expected direction. A different INIT cannot
replace an established session. On loss, retry exhaustion, or physical
transport disconnect, motion is stopped, outstanding delivery and duplicate
history are discarded, and the local nonce is rotated before negotiation. Both
nonce contributions therefore change across a replacement connection. A fresh
challenge prevents a completely buffered old handshake from re-establishing an
old generation. While negotiating, a later INIT may replace an incomplete
proposal, but cannot authorize motion.

States are DISCONNECTED, SESSION_NEGOTIATING, HEALTHY, DEGRADED, and LOST. No
MOTION is accepted before establishment. Heartbeat proves scoped peer liveness
but never authorizes or resumes motion. Reconnection establishes an empty,
no-motion session and requires fresh operator motion intent.

If the pendant reboots, renewals cease and the companion's local motion lease
expires; the new pendant nonce must handshake and old pendant traffic remains
invalid. If the companion reboots, it initializes with no motion and a new
nonce; the pendant times out its old generation and handshakes again. If both
reboot, neither nonce contribution nor motion state survives.

## Reliable delivery and sequences

Only one reliable packet is outstanding. The sender retains its exact encoded
bytes and retransmits those same bytes, session pair, and sequence after a NAK
or 150 ms ACK timeout. Three retries are allowed. Retry timing and age are
sender-local only. Exhaustion invalidates the session rather than reporting the
command delivered.

ACK and NAK carry the same session pair direction as any response and the
command sequence. A response from any other generation is ignored and cannot
complete or retransmit current work. The receiver dispatches a reliable command
once, then ACKs retransmissions without redispatch. Half-range serial arithmetic
accepts forward progress and rejects duplicates/old values; `65534, 65535, 0,
1` is valid within one session. A new session is a separate ordering domain.

## Receiver-local continuous-motion lease

All MOTION packets must be reliable and have exactly one motion action flag.
`MOTION_START` is fresh operator intent. After semantic acceptance the receiver
records its start sequence as the intent ID, authorizes software motion, and
starts a 300 ms lease using only the receiver's private monotonic clock.

`MOTION_RENEW` payload begins with the two-byte start sequence (intent ID). A
fresh, in-order renewal for the active, unexpired intent extends the deadline by
300 ms. The pendant should send renewals every 100 ms. A renewal is never sent
to the CNC semantic handler, so it cannot repeat incremental movement. A
retransmitted renewal is ACKed as a duplicate without redispatch or an extra
extension. A malformed, CRC-invalid, old-sequence, wrong-intent, old-session,
pre-handshake, or post-expiration renewal cannot extend or recreate a lease.
After expiration, only a new `MOTION_START` with a new sequence represents
fresh operator intent.

`MOTION_STOP` payload also begins with the intent ID. A valid STOP invokes the
semantic handler and terminates motion immediately. Successful STOP delivery is
not required for bounded stopping: if STOP is lost, the sender stops renewing
and the receiver-local lease expires. The same bound applies when a renewal is
lost, the cable is unplugged, the pendant crashes, or corruption prevents valid
renewals. Motion stops immediately when an explicit failure/STOP is processed,
or no later than local lease expiration after valid renewals cease. It is not
claimed to stop at the unknowable instant a silent failure occurs.

## Independent timers and defaults

| Setting | Default | Clock owner / purpose |
|---|---:|---|
| ACK_TIMEOUT_MS | 150 ms | sender-local reliable retry |
| MAX_RETRIES | 3 | sender-local bounded retry count |
| MOTION_RENEW_INTERVAL_MS | 100 ms | sender-local renewal schedule |
| MOTION_LEASE_MS | 300 ms | receiver-local continuous-motion watchdog |
| HEARTBEAT_INTERVAL_MS | 500 ms | each sender's local liveness cadence |
| LINK_LOST_TIMEOUT_MS | 2000 ms | receiver-local time since valid active-session traffic |

Each endpoint's monotonic clock is private to that endpoint. Receiver watchdog
and link decisions use receiver-local elapsed time. Sender retry and renewal
scheduling use sender-local elapsed time. No correctness or motion-safety rule
requires synchronized clocks, aligned epochs, clock-offset estimation, or
comparison of absolute monotonic timestamps between endpoints.

## Diagnostics

Diagnostics include packets sent/received, CRC failures, malformed packets,
ACK timeouts, NAKs, retransmissions, duplicates, retry exhaustion, last valid
local receive time, local heartbeat age, active session pair, session
establishments/resets, rejected old-session frames, rejected stale ACK/NAK,
lease renewals/expirations, rejected renewals, and link-loss events.
