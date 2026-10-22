# Known Limitations and Unverified Requirements

1. **Native Proteus file:** deterministic JSON connectivity, BOM, component-map and SVG review artifacts exist. A native .DSN/.PDSPRJ file has not been created/imported/rendered because a supported official Python writer/API was not confirmed. The native-project-status artifact is the source of truth.
2. **Physical bench:** the specified NodeMCU-32S and NXP TJA1051T/3 SO8 are now reflected in the board profile, source pin map and generated source artifacts. Physical PCB revision/header continuity, IC pin-1 orientation, supply/Silent-bias circuit and bench behavior are not yet measured. No firmware was flashed.
3. **CAN bus:** no vehicle bitrate/topology/safe tap point or identifier has been observed. No live capture or transmission on the Civic occurred.
4. **Host TX:** repeat scheduling, cancellation and audit work end-to-end on the virtual bus. The host has no physical TX control path. The firmware offers a guarded single-frame C API, but the CW1 protocol is read-only and does not expose host commands for it.
5. **Diagnostic workflows:** capability evidence/gates are implemented as metadata and simulation-only eligibility evaluation. No Honda-specific ECU address/service or executable vehicle diagnostic is shipped.
6. **Browser validation:** static files/API are covered by tests; no full cross-browser visual certification or device accessibility audit was performed.
7. **Performance:** benchmark figures reflect a synthetic single-host run, not UART/CAN throughput, physical real-time latency or multi-user server capacity.
8. **Network security:** server is local-only and unauthenticated; do not expose it externally. Any future remote-access feature needs authentication, CSRF protections appropriate to that deployment and a new threat review.
9. **Firmware/serial:** the firmware emits monotic observation/dequeue timestamps, not precise wire Start-of-Frame timestamps; the host bridge has not been tested on an actual hardware port.
10. **Independent validation:** when the operator promotes a mapping, the application records the supplied method and references. The software cannot independently verify the truth of external evidence.
