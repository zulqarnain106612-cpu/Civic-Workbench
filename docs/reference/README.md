# Owner-supplied reference material

Screenshots supplied by the project owner on 2026-10-23. They are the evidence cited by
`hardware/reference/esp32-tja1051-netlist.yaml` (facts F1-F8). Copyright NXP B.V.; kept for
internal design traceability only.

| File | Source | Used for |
|---|---|---|
| nxp-ah1014/ah1014-tja1051-block-diagram-and-pinning.jpg | AH1014 sec. 3, Fig 13 | F1: plain TJA1051 pin 5 n.c.; VIO/EN tied to VCC |
| nxp-ah1014/ah1014-tja1051-summary-pinout.jpg | AH1014 summary | pinout, Normal/Silent modes |
| nxp-ah1014/ah1014-tja1051-typical-application-5v-mcu.jpg | AH1014 typical application | reference application is a 5 V MCU |
| nxp-ah1014/ah1014-p72-vcc-pin-thermal-load.jpg | AH1014 7.1.1-7.1.2 | F6: VCC decoupling, supply current |
| nxp-ah1014/ah1014-p73-vcc-supply-current.jpg | AH1014 7.1.3 | supply buffer sizing |
| nxp-ah1014/ah1014-p74-vio-pin-and-bypass-capacitor.jpg | AH1014 7.1.4, Table 14 | F6: ~10 uF; VIO behaviour of /3 variant |
| nxp-ah1014/ah1014-p75-interface-and-mode-pins.jpg | AH1014 7.2-7.4 | TXD/RXD series resistor guidance |
| nxp-ah1014/ah1014-p76-split-termination.jpg | AH1014 7.4 | F7: split termination |
| nxp-ah1014/ah1014-p77-emc-optional-bus-circuitry.jpg | AH1014 8, Fig 45 | F7: optional bus parts |
| nxp-ah1014/ah1014-p90-pin-fmea-vbat-vcc.jpg | AH1014 10.1, Table 20 | pin short-circuit FMEA |
| nxp-ah1014/ah1014-p92-tja1051-fmea-gnd-open-neighbour.jpg | AH1014 Tables 21-22 | F4/F5: pin 5 open fail-safe; S open = no Silent |
| nxp-ah1014/ah1014-simulation-models.jpg | AH1014 10.3 | transceiver models are VHDL-AMS (not Proteus) |
| nodemcu-32s/nodemcu-32s-pinout.png | owner board pinout | header pins 33 (GPIO21), 36 (GPIO22), 38 (GND) |
