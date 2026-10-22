# S04 — Browser Engineering UI

## Delivered

- A responsive, dark engineering workbench is packaged under src/civic_workbench/web and served by the local application.
- The frame explorer presents sequence, monotonic timestamp, standard/extended ID, DLC, raw bytes, direction and capture-source provenance. It supports filtering by identifier, direction, source and payload.
- The timing chart and findings panel show observed timing and evidence-linked analysis output without treating candidate findings as verified vehicle mappings.
- The UI connects the capture, SQLite sessions, import/export, virtual lab, repeat/cancel TX scheduler, read-only CW1 serial status, and capability/mapping workflows through the same local API.
- TX authorization is visibly blocked for physical hardware; the UI has no hardware arm control.
- Static assets use a restrictive Content-Security-Policy, nosniff, no-referrer and no-store headers; the HTTP service rejects non-loopback Host values and cross-origin POST requests.

## Boundaries

The UI is a locally served application, not a remote-access dashboard. Current browser automation/browser-layout rendering has not been certified on every device. Hardware status can only become real when a user explicitly opens a read-only serial stream. The physical controller’s true bus state is never inferred from the simulator.

## Acceptance evidence

Browser assets, API route behavior, Host/Origin rejection, response headers, session workflows and simulation-driven UI APIs are covered by repository integration/security tests. The UI is not declared physically validated.
