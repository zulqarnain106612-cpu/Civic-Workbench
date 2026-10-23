# Proteus capture sheet - Rev B

Place these parts in Proteus ISIS and connect pins by net name (use terminals/net labels with exactly these names).
Generated from the reviewed netlist; regenerate with `make design-source` after any netlist change.

## Parts

| Ref | Value | Package | Fit |
|---|---|---|---|
| U1 | TJA1051T | SO8 | yes |
| R1 | 10k | 0805 | yes |
| R2 | 10k | 0805 | yes |
| R3 | 12k | 0805 | yes |
| R4 | 20k | 0805 | yes |
| C1 | 100nF X7R 16V | 0805 | yes |
| C2 | 10uF 16V | 1206 | yes |
| C3 | 100pF C0G | 0805 | DNP |
| C4 | 100pF C0G | 0805 | DNP |
| R5 | 60R 1% | 1206 | DNP |
| R6 | 60R 1% | 1206 | DNP |
| C5 | 4.7nF | 0805 | DNP |
| J2 | 3-pin CAN bench connector | 2.54 mm header | yes |
| J3 | 2-pin +5V bench supply input | 2.54 mm header | yes |
| J1 | NodeMCU-32S (use a header/connector symbol: GPIO22, GPIO21, GND) | board | yes |

## Nets

| Net | Members |
|---|---|
| +5V_CAN | C1.1, C2.1, J3.1, R1.2, R2.2, U1.3 |
| CANH | J2.1, U1.7 |
| CANL | J2.2, U1.6 |
| GND | C1.2, C2.2, J1.GND, J2.3, J3.2, R4.2, U1.2 |
| RXD_3V3 | J1.GPIO22, R3.2, R4.1 |
| RXD_5V | R3.1, U1.4 |
| S_SILENT | R1.1, U1.8 |
| TXD_5V | R2.1, U1.1 |

No-connect (place no-connect markers): J1.GPIO21, U1.5
