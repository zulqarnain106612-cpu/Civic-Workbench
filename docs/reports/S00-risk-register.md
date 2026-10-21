# S00 — Risk Register

| ID | Risk | Severity | Status | Mitigation / exit evidence |
|---|---|---|---|---|
| S00-R01 | User development computer is offline; local OS/toolchain/repository state cannot be inspected | High | Open; blocks S00 completion | Reconnect Desktop Commander and attach timestamped, read-only command output to this report/manifest |
| S00-R02 | Exact ESP32 board/module and available GPIOs are unknown | High | Open | Inspect markings and datasheet; confirm flash/PSRAM reservations and boot-strapping pins before TXD/RXD selection |
| S00-R03 | Proteus version and licensed capabilities are unknown | Medium-High | Open | Inspect Help/About, installed libraries/docs and product version after reconnect |
| S00-R04 | Public Labcenter pages checked did not confirm a supported Python API to generate native schematic/project files | High for S09 schedule | Open | Verify installed official documentation or obtain confirmation from Labcenter; prove any candidate API with a minimal native project |
| S00-R05 | CAN bit rate, network topology, connector/pinout and safe capture point are unknown | High | Open | Establish through trustworthy vehicle-specific evidence and controlled physical inspection; do not guess |
| S00-R06 | Original ESP32 TWAI cannot process CAN-FD frames | Medium-High | Conditional/unknown vehicle compatibility | Confirm target bus protocol/format before assuming the fixed MCU supports every vehicle segment |
| S00-R07 | Future TX could disrupt an active vehicle bus if safety depends only on software | High | Mitigated by requirements, not implemented | Physical hardware inhibit plus firmware policy, deliberate arming, bounded scheduler, audit and abort; bench/simulation gate first |
| S00-R08 | Initial repository contains specifications but no executable acceptance tests or implementation | Medium | Known | S01 adds machine-checked schemas/contracts; keep all requirements open until tests and evidence exist |

## Rules

- A severity is not a claim that an incident has occurred.
- "Open" means the evidence needed to close the risk has not yet been collected.
- An official website search cannot substitute for checking the installed product's files or contacting the vendor when a specific supported API must be proven.
- No risk is closed solely because a document has been written.
