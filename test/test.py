# SPDX-FileCopyrightText: © 2026 Raghav Vijayapal
# SPDX-License-Identifier: Apache-2.0
#
# Tests for the HZN-1 Mode S CRC-24 checker, using real ADS-B messages from aircraft and a Python model of the CRC.

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

POLY = 0xFFF409
DONE, OK, BAD, LONG, BUSY = 1, 2, 4, 8, 16
DATA, STROBE, START = 1, 2, 4

# Real DF17 extended squitters. KLM1023 is the identification message the HZN-1 site follows through the chip.
KLM1023 = "8D4840D6202CC371C32CE0576098"
REAL = [
    KLM1023,
    "8D40621D58C382D690C8AC2863A7",  # airborne position (even)
    "8D40621D58C386435CC412692AD6",  # airborne position (odd)
    "8D485020994409940838175B284F",  # airborne velocity
    "8DA05F219B06B6AF189400CBC33F",  # airborne velocity, airspeed subtype
    "8D406B902015A678D4D220AA4BDA",  # identification
]
SHORT = "5D4840D6F8740F"  # a 56-bit all-call reply (format 11) from the same aircraft


def bits_of(hexmsg):
    n = len(hexmsg) * 4
    return [int(b) for b in bin(int(hexmsg, 16))[2:].zfill(n)]


def model(bits):
    """What the hardware does each time a bit arrives."""
    rem = 0
    for b in bits:
        fb = ((rem >> 23) & 1) ^ b
        rem = ((rem << 1) & 0xFFFFFF) ^ (POLY if fb else 0)
    return rem


async def setup(dut):
    cocotb.start_soon(Clock(dut.clk, 100, unit="ns").start())  # 10 MHz
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)


async def start(dut):
    dut.ui_in.value = START
    await ClockCycles(dut.clk, 3)
    dut.ui_in.value = 0
    await ClockCycles(dut.clk, 3)


async def send(dut, bits):
    for b in bits:
        dut.ui_in.value = b * DATA
        await ClockCycles(dut.clk, 1)
        dut.ui_in.value = b * DATA | STROBE
        await ClockCycles(dut.clk, 2)
        dut.ui_in.value = b * DATA
        await ClockCycles(dut.clk, 1)
    dut.ui_in.value = 0
    await ClockCycles(dut.clk, 4)  # let the last bit through the synchronisers


def status(dut):
    return int(dut.uo_out.value) & 0x1F


async def read(dut, view, sel):
    dut.ui_in.value = (view << 5) | (sel << 3)
    await ClockCycles(dut.clk, 1)
    v = int(dut.uio_out.value)
    dut.ui_in.value = 0
    return v


async def check(dut, bits):
    """Send one message from a fresh start and compare everything the chip reports with the model."""
    await start(dut)
    await send(dut, bits)
    rem = model(bits)
    want = DONE | (OK if rem == 0 else BAD) | (LONG if bits[0] else 0)
    assert status(dut) == want, f"status {status(dut):05b}, expected {want:05b}"
    syn = [await read(dut, 1, s) for s in (1, 2, 3)]
    assert syn == [rem >> 16, (rem >> 8) & 0xFF, rem & 0xFF], f"syndrome {syn}, expected {rem:06X}"
    assert await read(dut, 1, 0) == len(bits)
    return rem


@cocotb.test()
async def test_klm1023(dut):
    """The real KLM1023 message passes, and the chip reads back its ICAO address 4840D6."""
    await setup(dut)
    assert await check(dut, bits_of(KLM1023)) == 0
    head = [await read(dut, 0, s) for s in range(4)]
    assert head == [0x8D, 0x48, 0x40, 0xD6], f"read back {bytes(head).hex()}"
    dut._log.info("KLM1023: check code OK, ICAO 4840D6, format 17")


@cocotb.test()
async def test_real_messages(dut):
    """Six real ADS-B broadcasts all pass."""
    await setup(dut)
    for m in REAL:
        assert await check(dut, bits_of(m)) == 0, m


@cocotb.test()
async def test_short_message(dut):
    """A 56-bit message is recognised as short from its first bit and checked over 56 bits."""
    await setup(dut)
    assert await check(dut, bits_of(SHORT)) == 0
    assert [await read(dut, 0, s) for s in (1, 2, 3)] == [0x48, 0x40, 0xD6]


@cocotb.test()
async def test_every_single_bit_flip(dut):
    """Flipping any one of KLM1023's 112 bits is caught, and the syndrome matches the model."""
    await setup(dut)
    good = bits_of(KLM1023)
    for i in range(112):
        bad = good.copy()
        bad[i] ^= 1
        if i == 0:
            continue  # flipping the first bit turns it into a short message; covered by the random test
        assert await check(dut, bad) != 0, f"bit {i} flip slipped through"
    dut._log.info("all single-bit flips of KLM1023 caught")


@cocotb.test()
async def test_random(dut):
    """Random valid messages pass; random corruptions fail exactly when the model says so."""
    await setup(dut)
    rng = random.Random(1023)
    for k in range(30):
        n = rng.choice((56, 112))
        data = [1 if n == 112 else 0] + [rng.randint(0, 1) for _ in range(n - 25)]
        p = model(data)
        msg = data + [(p >> (23 - j)) & 1 for j in range(24)]
        if k % 2:
            for j in rng.sample(range(1, n), rng.randint(1, 4)):
                msg[j] ^= 1
        await check(dut, msg)


@cocotb.test()
async def test_start_mid_message_and_extra_bits(dut):
    """START clears a half-received message, and bits after the last one are ignored."""
    await setup(dut)
    await send(dut, bits_of(REAL[3])[:40])
    assert status(dut) == BUSY | LONG
    await check(dut, bits_of(KLM1023))
    await send(dut, [1, 0, 1, 1])
    assert status(dut) == DONE | OK | LONG
    assert await read(dut, 1, 0) == 112
