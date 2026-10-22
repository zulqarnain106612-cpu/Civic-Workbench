# ADR-0002: Physical CAN transmission is disabled by default

Status: Accepted

S03 firmware keeps hardware init, verified bitrate and TX capability behind disabled-by-default build options and an inactive TX gate. The host serial protocol is read-only. Host raw-frame TX and repeats operate only on the virtual bus. This avoids accidentally turning a local engineering UI into a vehicle command endpoint before the exact board, bitrate, wiring and independent physical interlock are reviewed. Capability schemas can document possible diagnostic support without executing it.
