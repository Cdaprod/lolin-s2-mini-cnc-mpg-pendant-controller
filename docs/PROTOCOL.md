# Reliable pendant protocol

## Architecture assessment

`src.transport.base` owns the replaceable byte-stream contract and UART/mock
backends. `src.transport.protocol` owns the codec, bounded streaming parser,
reliable session, and link diagnostics. The existing `GRBLController` remains
the CNC command adapter/dispatcher; stock GRBL is **not** assumed to understand
this framing. `PendantState` exposes link health to UI view models without a
renderer dependency. A companion endpoint may place this session between the
pendant and a GRBL/grblHAL adapter.

## Wire format

All integers are big-endian. A frame is:

| Field | Bytes | Meaning |
|---|---:|---|
| SOF | 1 | `0xA5` |
| version | 1 | `1` |
| packet type | 1 | DATA=1, ACK=2, NAK=3, HEARTBEAT=4, CONTROL=5 |
| sequence | 2 | modulo-65536 identifier |
| message class | 1 | SAFETY, MOTION, COMMAND, STATUS, CONFIG, or FILE |
| flags | 1 | bit 0 requests reliable delivery |
| payload length | 2 | 0..256 |
| sender monotonic milliseconds | 4 | modulo-2^32 motion-age timestamp |
| payload | 0..256 | endpoint-defined bytes |
| CRC | 2 | CRC-16/CCITT-FALSE over version through payload |
| EOF | 1 | `0x5A` |

CRC uses polynomial `0x1021`, initial value `0xFFFF`, no reflection, and no
final XOR. The maximum encoded frame is 272 bytes. Length is rejected before
payload buffering can exceed that bound. Invalid versions, types, lengths,
terminators, and CRCs are never dispatched; the parser scans for the next SOF.

## Reliability and health

One reliable packet may be outstanding. ACK must match its sequence. NAK or a
150 ms timeout retransmits the identical bytes and sequence, at most three
times. The receiver uses modulo-65536 half-range serial arithmetic so duplicate
and older sequence IDs are ACKed again but never dispatched. Sequence IDs wrap
after 65535. HEARTBEAT is sent every 500 ms. Link states are DISCONNECTED,
CONNECTING, HEALTHY, DEGRADED, and LOST; no valid packet for 2000 ms is LOST.
Retry exhaustion also fails closed and invokes the supplied jog-stop callback.

MOTION defaults to a 250 ms lifetime and is NAKed without dispatch when stale.
Both protocol endpoints must use a common monotonic millisecond epoch (or an
adapter-provided synchronized offset) for motion timestamps. Continuous jog is
represented by refreshed, expiring motion state; it must not be an unbounded
queue of incremental moves. Link loss cancels software jogging. This protocol
does not provide emergency-stop or functional-safety guarantees; the physical
hardwired E-stop remains an independent safety layer.
