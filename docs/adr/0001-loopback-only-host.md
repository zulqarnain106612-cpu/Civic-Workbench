# ADR-0001: Loopback-only host service

Status: Accepted

The local HTTP API uses no authentication in this initial single-user workstation scope, so it must bind only to loopback, reject external Host values and enforce same-origin POST semantics. Remote access is not enabled. A future remote deployment requires a separate authentication/session/CSRF/threat-model decision and cannot be achieved by merely changing the bind address.
