# S02 Hardware Foundation — TX Inhibit and Transceiver Interface

**Status:** Rev B receive-only interface defined in `hardware/reference/esp32-tja1051-netlist.yaml` and generated into `hardware/proteus/generated/`. NodeMCU-32S and the NXP TJA1051 marked NXP TJA1051 25 06 ND312 stay fixed; no substitute. The marking is not decoded into an orderable type; the owner-supplied datasheet and AH1014 pages (`docs/reference/`) describe the pin-5 n.c. type, which is not yet confirmed for the installed IC. Electrical checks pass on paper; nothing is bench-measured yet.

## Rev B controller/transceiver connections (receive-only)

| Function | TJA1051 SO8 pin | Rev B connection |
|---|---:|---|
| TXD | 1 | Not driven by the ESP32. R2 10k to +5V_CAN holds it recessive. (TXD VIH = 0.7 x VCC = 3.5 V; 3.3 V GPIO cannot meet it.) |
| GND | 2 | Common ground: bench supply, NodeMCU GND (header 38), CAN ground |
| VCC | 3 | +5V_CAN from a current-limited 4.5-5.5 V bench supply; C1 100 nF at the pin, C2 10 uF |
| RXD | 4 | R3 12k / R4 20k divider to GPIO22 (header 36): <= 3.44 V at VCC 5.5 V |
| n.c. | 5 | Left open. Fail-safe for every TJA1051 variant (AH1014 Table 21) |
| CANL | 6 | J2 pin 2 |
| CANH | 7 | J2 pin 1 |
| S | 8 | R1 10k to +5V_CAN = Silent whenever U1 is powered. No MCU connection. |

GPIO21 (TWAI_TX, header 33) is reserved and left unconnected in Rev B.

Source: [NXP TJA1051 official datasheet](https://www.nxp.com/docs/en/data-sheet/TJA1051.pdf).

## Fail-safe operating requirements

1. Pin S must have an external pull-up to the transceiver VCC rail (not the 3.3 V logic rail, which is below S VIH = 3.5 V) so reset, high-impedance GPIO, MCU boot and loss of firmware power default to Silent mode.
2. Do **not** connect the MCU GPIO directly to S as the only protection.
3. (Future TX revision only) Implement a hardware-only path that can pull S LOW only when both (a) the external physical interlock is closed and (b) the firmware TX-enable request is asserted. Use an electrically reviewed gate/series-switch design with documented default-off bias; validate leakage, voltage domains and fault behavior before assembly.
4. The MCU TX-enable request must have an external default-off pull-down. The physical interlock must interrupt the electrical path independently of firmware. Software GPIO readback is status feedback, not the safety barrier.
5. If an interlock feedback signal is available, route it to a separately selected input GPIO. Disagreement or unknown feedback must deny TX.
6. Keep the controller in TWAI_MODE_LISTEN_ONLY for S02. S02 does not expose a frame-transmit command.
7. Do not connect CANH/CANL to GPIO. Do not add termination to an existing vehicle network without understanding the topology.
8. On reset, failure, bus-off, stop, or disarm, the firmware request must return inactive. The external circuit must still hold S HIGH without a powered MCU.
9. GPIO21/TWAI_TX and GPIO22/TWAI_RX are the source-selected NodeMCU-32S mapping; verify the physical board revision/header continuity and review flash/strapping restrictions before wiring.

## Current firmware behavior

The PlatformIO board target is **NodeMCU-32S (nodemcu-32s), classic ESP32 only**. TWAI GPIO mapping is GPIO21 TX / GPIO22 RX. CONFIG_CIVIC_ALLOW_HARDWARE_CAN_INIT, CONFIG_CIVIC_BITRATE_EVIDENCE_CONFIRMED, and CONFIG_CIVIC_ALLOW_HARDWARE_CAN_TX remain disabled. A compile-time bitrate default is only a placeholder; it is not established vehicle bitrate evidence. Rev B holds S HIGH with R1 to +5V_CAN and leaves pin 5 open; no GPIO or firmware control can pull S LOW. A receive-only firmware build (`CONFIG_CIVIC_RECEIVE_ONLY_BENCH`) starts TWAI in listen-only mode without TX gate or interlock GPIOs.

## Open hardware evidence

- [x] Exact board baseline recorded: ESP32S NodeMCU / NodeMCU-32S, classic ESP32.
- [x] Source mapping established: GPIO21/TWAI_TX and GPIO22/TWAI_RX.
- [x] Exact transceiver identity and marking retained: NXP TJA1051 marked NXP TJA1051 25 06 ND312; no substitute.
- [ ] Physical board silkscreen/revision and GPIO21/GPIO22 header continuity checked with a meter.
- [ ] Confirm physical SO8 pin-1 orientation and footprint before wiring.
- [x] Pin 5 left open: electrically fail-safe for n.c., VIO and EN variants (AH1014 Table 21).
- [ ] Confirm the installed U1 pin-5 function; Rev B receives only if pin 5 is n.c.
- [x] Supply decoupling, Silent-mode bias, RXD level shifting and connectors defined in Rev B (design-checks.json passes).
- [ ] Power U1 alone; measure +5V_CAN, S >= 3.5 V and RXD_3V3 <= 3.6 V before connecting GPIO22.
- [ ] Bench-verify Silent-mode behavior and reset/power-loss state with the exact parts.
- [ ] hardware/proteus/generated/civic-workbench-rev-b-sim.edf imported in a licensed Proteus (File > Import ECAD Files), saved as .pdsprj, simulated, and the evidence recorded.
- [ ] Vehicle topology/bitrate/capture-point evidence (separate vehicle discovery task).
