# Security and Safety Review

## Host boundary

The application server uses Python's standard-library threaded HTTP server, binds to loopback by default and refuses non-loopback host configuration. The Host header is allowlisted; POST requests with an Origin must match the same local origin. Static responses include CSP, X-Content-Type-Options, Referrer-Policy and Cache-Control: no-store. Request bodies are limited to 4 MiB. Static file serving uses a fixed filename allowlist rather than arbitrary filesystem paths.

The local server is unauthenticated. Loopback/origin checks are not a substitute for authentication, and users must not expose this service via port-forwarding, reverse proxy or shared-network bind. Browser users should open the local application directly, not embed it into a third-party page.

## Persistence

SQLite binds are parameterized. Imported bundles are validated as a complete unit before a transaction. File paths are regenerated locally instead of trusting an external raw_capture path. Raw capture records are stored independently of findings and mapping versions. Exports carry payload data and must be treated as potentially sensitive vehicle information.

## CAN safety boundary

- Hardware TX capability and controller initialization remain disabled in firmware configuration by default.
- Bitrate evidence and GPIO configuration remain unconfirmed/unassigned.
- Host TX is simulation-only; requests to other targets are rejected and audited.
- The serial bridge is read-only and sends no bytes to the device.
- Diagnostic capability workflow endpoints evaluate eligibility only and do not execute diagnostic protocol operations.
- The controller C API performs a final guard at call time, but code-based policy cannot replace an independently implemented hardware TX gate, default-Silent transceiver bias, correct power sequencing and verified physical interlock.
- The physical board, transceiver circuit, serial behavior and Civic network have not been bench or vehicle tested.

## Data interpretation

Raw frame capture source/timestamps remain preserved. Analysis results are annotations that refer to frame UUIDs. Candidate and validated are different statuses; automatic analysis cannot promote a candidate. Simulation/import traffic is never presented as verified physical vehicle traffic.
