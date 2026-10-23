# Known Limitations and Unverified Requirements

1. **Native Proteus file:** the Rev B schematic SVG, netlist, BOM, design checks and a Proteus capture sheet are generated. A native .pdsprj has not been created: no official Python writer exists, the installed Proteus is a demonstration profile, and the generating session had no shell on the Proteus host. See native-project-status.json.
2. **Physical bench:** Rev B receive-only interface values are defined and checked on paper (design-checks.json). Header continuity, pin-1 orientation, Silent-bias and RXD levels, and bench behaviour are not yet measured. No firmware was flashed.
3. **CAN bus:** no vehicle bitrate/topology/safe tap point or identifier has been observed. No live capture or transmission on the Civic occurred.
4. **Host TX:** Rev B hardware cannot transmit (TXD not wired, S tied HIGH). repeat scheduling, cancellation and audit work end-to-end on the virtual bus. The host has no physical TX control path. The firmware offers a guarded single-frame C API, but the CW1 protocol is read-only and does not expose host commands for it.
5. **Diagnostic workflows:** capability evidence/gates are implemented as metadata and simulation-only eligibility evaluation. No Honda-specific ECU address/service or executable vehicle diagnostic is shipped.
6. **Browser validation:** static files/API are covered by tests; no full cross-browser visual certification or device accessibility audit was performed.
7. **Performance:** benchmark figures reflect a synthetic single-host run, not UART/CAN throughput, physical real-time latency or multi-user server capacity.
8. **Network security:** server is local-only and unauthenticated; do not expose it externally. Any future remote-access feature needs authentication, CSRF protections appropriate to that deployment and a new threat review.
9. **Firmware/serial:** the firmware emits monotic observation/dequeue timestamps, not precise wire Start-of-Frame timestamps; the host bridge has not been tested on an actual hardware port.
10. **Independent validation:** when the operator promotes a mapping, the application records the supplied method and references. The software cannot independently verify the truth of external evidence.
