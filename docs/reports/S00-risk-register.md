# S00 — Risk Register

**Updated:** 2026-10-22 after live host inspection.

| ID | Risk / unknown | Severity | Status | Mitigation / closure evidence |
|---|---|---|---|---|
| S00-R01 | Remote machine availability prevented the first inspection attempt | Medium | **Closed** | Device subsequently reported Online; successful shell commands collected on `s752-LIFEBOOK-S752` |
| S00-R02 | Exact original ESP32 module/board and available GPIOs are unknown | High | Open; S02 dependency | Inspect board markings/datasheet when the board is available; validate boot-strapping, flash-reserved pins and actual exposed GPIOs before assignment |
| S00-R03 | The shell does not have a usable standalone firmware toolchain yet | High | Open; S02 dependency | Select and pin a reproducible route; supply required core dependencies and compile a minimal TWAI firmware target for original ESP32 |
| S00-R04 | Cached compiler is for ESP32-S3 and RISC-V targets, not classic ESP32 | High | Open; S02 dependency | Install/resolve the classic ESP32 compiler; prove target build with explicit chip target and build output |
| S00-R05 | Proteus license/activation and exact enabled modules are unknown | Medium | Open | Inspect Help/About/activation state or confirm with account/vendor; don't assert licensed capabilities from path names |
| S00-R06 | Installed/public material did not establish a supported official Python API for native schematic generation | High for S09 | Open; S09 dependency | Read installed ISIS help/vendor documentation or obtain written Labcenter confirmation; create and open a minimal native schematic from the selected generation route |
| S00-R07 | Vehicle bit rate, network topology, protocol/frame format and safe capture point are unknown | High | Open; vehicle discovery dependency | Use reliable vehicle-specific evidence and a controlled passive capture; never guess a bus rate or ID |
| S00-R08 | Physical TJA1051T/3 presence and assembled hardware are unverified | Medium-High | Open; S02 dependency | Confirm part marking/orientation, inspect final schematic, then bench-test supply/mode/TXD/RXD before connecting to any vehicle network |
| S00-R09 | Original ESP32 TWAI is Classical CAN, not CAN FD | Medium-High | Constraint confirmed; vehicle compatibility unknown | Establish which bus segment and frame format are present before assuming fixed MCU can observe all networks |
| S00-R10 | TX safety is a requirement but has not been implemented | High | Controlled by design constraints, not yet mitigated in hardware/software | Make hardware Silent-mode inhibit and firmware policy a mandatory tested design; simulation/isolated bench before active vehicle TX |
| S00-R11 | No application or firmware implementation/tests exist yet in the inspected repository | Medium | Known baseline | Proceed to S01 interface schemas/contract tests, then S02 and beyond; never report spec files as working features |

## Severity guidance

A high-severity item represents a risk if implementation proceeds without resolving it, not an assertion that an incident has occurred. "Open" means evidence is missing. Risk closure requires an artifact, command result, or review record.
