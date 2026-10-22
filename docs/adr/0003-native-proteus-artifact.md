# ADR-0003: Do not fabricate an unsupported native Proteus project

Status: Accepted

The native Proteus schematic format is not treated as an ordinary text file. Local installed samples are packaged binaries and an official Python writer/automation API was not confirmed. The project generates deterministic structured connectivity, BOM, component-map and SVG review artifacts, and records native project creation/import as blocked. It will only claim a native project after an official supported API/utility is confirmed and the resulting project actually imports/renders in Proteus.
