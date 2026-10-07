<!---
This file is used to generate your project datasheet.
-->

## How it works

Every aircraft with ADS-B broadcasts Mode S messages on 1090 MHz: 112 bits for the long "extended squitter"
messages that carry position, velocity and call sign, and 56 bits for short replies. The last 24 bits of every
message are a check code made with the generator polynomial 0x1FFF409, so a receiver can throw away anything
damaged on the way.

This design is that check, the first real piece of the HZN-1 concept chip (an ADS-B decoder and fuel estimator):

- Bits go in one at a time: set `DATA`, then raise `STROBE`. The pins are synchronised, so any slow source works.
- A 24-bit shift register divides the message by the generator as it arrives. The first bit tells it the length:
  formats 16 and up start with a 1 and are 112 bits, the rest are 56.
- After the last bit, `DONE` goes high along with `OK` (the remainder is zero) or `BAD`.
- The first 32 bits are kept, so the plane's 24-bit ICAO address can be read back on the `READ` pins.
- The remainder (the syndrome) can also be read back. Real decoders use it to find and fix a single wrong bit.

## How to test

1. Pulse `START` high to clear.
2. For each bit, most significant first: set `DATA`, then take `STROBE` high and low again (at least two clock
   cycles each way at 10 MHz).
3. Watch `DONE`, `OK` and `BAD`. `LONG` shows the message length and `BUSY` is high part way through.
4. Read back with `VIEW` and `SEL`:

| VIEW | SEL | READ[7:0] |
|------|-----|-----------|
| 0 | 0 | first byte (downlink format and capability) |
| 0 | 1, 2, 3 | ICAO address, high to low byte |
| 1 | 0 | number of bits received |
| 1 | 1, 2, 3 | syndrome, high to low byte (all zero when OK) |

Example: KLM1023's identification message `8D4840D6202CC371C32CE0576098` gives `DONE`, `OK` and `LONG`, and reads
back `8D`, `48`, `40`, `D6`. Flipping any single bit gives `BAD`.

## External hardware

None. The demo board's microcontroller can feed messages in; a 1090 MHz receiver front end would be the next step.
