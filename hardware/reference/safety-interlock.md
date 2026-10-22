# S02 Hardware Foundation — TX Inhibit and Transceiver Interface

**Status:** NodeMCU-32S plus the exact physical NXP TJA1051 marked `NXP TJA1051 25 06 ND312` are the fixed baseline. The orderable suffix is not inferred. This is an electrical design contract, not a validated schematic or assembled circuit. GPIO21/GPIO22 are source-mapped; physical header continuity and PCB revision remain unmeasured. Do not wire pin 5 or power the transceiver until NXP confirms its exact variant/function.

## Required controller/transceiver connections

| Function | NXP TJA1051 SO8 pin | Required relationship |
|---|---:|---|
| TXD | 1 | ESP32S NodeMCU GPIO21 / TWAI_TX, after pin-1 orientation is checked |
| GND | 2 | Common logic/transceiver ground |
| VCC | 3 | Regulated supply within the NXP datasheet range, 4.5–5.5 V |
| RXD | 4 | ESP32S NodeMCU GPIO22 / TWAI_RX, after pin-1 orientation is checked |
| Variant-dependent | 5 | **Unresolved for the exact marked item; leave unconnected pending NXP confirmation. Do not presume VIO or EN.** |
| CANL | 6 | Physical CAN low |
| CANH | 7 | Physical CAN high |
| S | 8 | Receive-only baseline: external bias HIGH = Silent, receiver active and transmitter disabled. No direct MCU GPIO control. |

Source: [NXP TJA1051 official datasheet](https://www.nxp.com/docs/en/data-sheet/TJA1051.pdf).

## Fail-safe operating requirements

1. Pin S must have an external pull-up to the logic supply so reset, high-impedance GPIO, MCU boot and loss of firmware power default to Silent mode.
2. Do **not** connect the MCU GPIO directly to S as the only protection.
3. Implement a hardware-only path that can pull S LOW only when both (a) the external physical interlock is closed and (b) the firmware TX-enable request is asserted. Use an electrically reviewed gate/series-switch design with documented default-off bias; validate leakage, voltage domains and fault behavior before assembly.
4. The MCU TX-enable request must have an external default-off pull-down. The physical interlock must interrupt the electrical path independently of firmware. Software GPIO readback is status feedback, not the safety barrier.
5. If an interlock feedback signal is available, route it to a separately selected input GPIO. Disagreement or unknown feedback must deny TX.
6. Keep the controller in TWAI_MODE_LISTEN_ONLY for S02. S02 does not expose a frame-transmit command.
7. Do not connect CANH/CANL to GPIO. Do not add termination to an existing vehicle network without understanding the topology.
8. On reset, failure, bus-off, stop, or disarm, the firmware request must return inactive. The external circuit must still hold S HIGH without a powered MCU.
9. GPIO21/TWAI_TX and GPIO22/TWAI_RX are the source-selected NodeMCU-32S mapping; verify the physical board revision/header continuity and review flash/strapping restrictions before wiring.

## Current firmware behavior

The PlatformIO board target is **NodeMCU-32S (nodemcu-32s), classic ESP32 only**. TWAI source mapping is GPIO21 TX / GPIO22 RX. Hardware initialization, bitrate confirmation and physical TX remain disabled. The exact visible transceiver marking is `NXP TJA1051 25 06 ND312`; do not infer `/3` or `/E` from it. Because NXP variants differ at pin 5, leave pin 5 unconnected and do not power the circuit until NXP confirms its function for this exact item. A compile-time bitrate default is only a placeholder, not evidence of vehicle bitrate.

## Open hardware evidence

- [x] Exact board baseline recorded: ESP32S NodeMCU / NodeMCU-32S, classic ESP32.
- [x] Source mapping established: GPIO21/TWAI_TX and GPIO22/TWAI_RX.
- [x] Exact visible marking recorded verbatim: NXP TJA1051 25 06 ND312; orderable suffix not inferred.
- [ ] Physical board silkscreen/revision and GPIO21/GPIO22 header continuity checked with a meter.
- [ ] Confirm physical SO8 pin-1 orientation and footprint before powering the circuit.
- [ ] Obtain NXP confirmation for the exact visible marking and pin-5 function; the prior `/3` assumption is withdrawn.
- [ ] Obtain NXP confirmation for the exact marked item and pin-5 function; do not infer a suffix or classify marking characters without evidence.
- [ ] Complete and review supply decoupling, Silent-mode bias, connector and protection details.
- [ ] Bench-verify Silent-mode behavior and reset/power-loss state with the exact parts.
- [ ] Native Proteus generation/import verification (separate design task).
- [ ] Vehicle topology/bitrate/capture-point evidence (separate vehicle discovery task).
