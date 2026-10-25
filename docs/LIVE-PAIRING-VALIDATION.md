# ESP-NOW live pairing validation

## Baseline

PR #16 and #17 are merged into `main`. CI tests pass, but hardware pairing is not yet verified end-to-end.

## Bench evidence

- XIAO ESP32-S3 CircuitPython 10.3.1 running full round UI, connected to Wi-Fi `cda_Lab` channel 9.
- ESP32-C3 bridge ESP-IDF on channel 9 repeatedly accepts `PAIR v1` from S3 MAC `28:84:85:b3:90:f0`.
- S3 still displays DISCONNECTED / CONTROLLER OFFLINE. This state may mean PAIR_ACK wasn't received/accepted, or that GRBL status is absent; these must be distinguished.
- S3 runtime now logs RX frames, PAIR_ACK count, accepted ACK, rejection causes, and summary every 10 seconds.

## Next bench test

1. Pull and deploy latest `main` or this branch onto CircuitPython S3; do not reflash C3 yet.
2. Observe `[espnow] paired=... rx=... pair_acks=... good=... bad=... last_error=...` and C3 serial PAIR logs simultaneously.
3. If RX=0, investigate C3 send delivery and address/channel. If ACK arrives but is rejected, compare protocol payload/header/session/MAC with C3 protocol implementation.
4. If `paired=True` but controller offline, test GRBL UART/status freshness separately.
5. Keep MPG_BRIDGE_MOTION_ENABLED=false and physical inputs disabled until electrical validation; radio pairing is not authority for machine motion.

## Acceptance

- Bidirectional pairing and heartbeat proven over multiple S3 restarts, with proper timeout/reconnect handling.
- GRBL status can be observed and rendered, no unsafe automatic motor/jog activation.
- Unit tests and GitHub Actions pass.
