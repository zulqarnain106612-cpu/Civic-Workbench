# Fault and Recovery Matrix

| Condition | Detection | Expected behavior | Evidence / recovery |
|---|---|---|---|
| Local service cannot bind | HTTP server startup exception | Process exits; no remote listen fallback | Correct the selected local port |
| Non-loopback Host | Host allowlist | HTTP 403; no route action | Use 127.0.0.1 / localhost |
| Cross-origin POST | Origin/Host comparison | HTTP 403; no route action | Serve UI from the local service origin |
| Invalid or oversized JSON | Body cap, UTF-8/JSON parse, schema validator | 422 response; no record written | Correct request and retry |
| Unknown route | Route allowlist | 404 structured response | Use documented API route |
| Session/frame UUID collision | SQLite uniqueness constraints | Conflict; existing raw frame is retained | Use a new session/import ID |
| Append after finalization | Session ended timestamp | Conflict; raw capture is not reopened | Start a new session |
| Corrupt or unsafe bundle | Schema/evidence/path validation before transaction | Reject before mutation; rollback on insert error | Repair the source bundle |
| Disk unavailable / write failure | SQLite/file exception | Error log; operation fails, not silently acknowledged | Restore disk access and use SQLite integrity checks |
| Serial port absent/in use | pySerial open error | Visible error; no fallback port scan | Check the explicitly selected device/permissions |
| Oversized/malformed CW1 line | Line-size cap and JSON/schema validation | Increment malformed counter and ignore record | Inspect device UART output |
| Serial link loss | read-loop exception/stop state | Status becomes disconnected; stored records remain | Reconnect to the explicit port |
| TWAI/app RX queue overflow | Software drop counter; TWAI missed/overrun stats | Record loss is surfaced; armed TX is disarmed on app-queue overflow | Inspect counters and reduce/repair load |
| TWAI bus-off | Controller state/status | Software disarm; recovery is explicit and restart remains disarmed | Inspect the physical bus before recovery |
| Physical interlock open | GPIO sense input and external hardware gate | Firmware refuses/disarms software TX; external gate must independently inhibit TX | Inspect hardware circuit; do not bypass gate |
| TX request sent to hardware host target | Central host boundary | Rejected and audited; physical_tx_performed=false | Use only the simulation target |
| Simulator queue/emission bound exceeded | Preflight size limits | Reject the step/replay rather than allocate an unlimited event backlog | Advance in smaller virtual-time increments |
| Unknown diagnostic capability | Status/evidence contract gate | Remains disabled; workflow denied | Collect independent evidence before enabling |
| Unknown parameter byte order/scale | Explicit decoder input validation | No decode until operator specifies assumptions; saved mappings start candidate | Record the definition method and independent evidence |
| Native Proteus automation not available | Generator status artifact | Native project marked blocked; JSON/SVG source is not mislabeled as native | Confirm official Labcenter automation and perform actual import/render |
