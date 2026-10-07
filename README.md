![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# HZN-1 real silicon: Mode S CRC-24 checker

The first real piece of [HZN-1](https://hzn1.com/), a concept chip that listens to aircraft
ADS-B broadcasts and estimates each plane's fuel. This block checks the 24-bit code at the end of every Mode S
message and reads back the aircraft's ICAO address, built as a real chip layout for the SkyWater SKY130 process
through [Tiny Tapeout](https://tinytapeout.com).

- Design: [src/project.v](src/project.v)
- Tests, using real ADS-B messages including KLM1023: [test/test.py](test/test.py)
- Datasheet: [docs/info.md](docs/info.md)

The GitHub Actions here run the tests, harden the design into a GDS layout with LibreLane, run Tiny Tapeout's
precheck, repeat the tests on the gate-level netlist and publish a 3D viewer of the layout.

Made by Raghav Vijayapal.
