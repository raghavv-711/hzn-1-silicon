/*
 * HZN-1 real silicon: a Mode S / ADS-B CRC-24 message checker.
 * Copyright (c) 2026 Raghav Vijayapal
 * SPDX-License-Identifier: Apache-2.0
 *
 * Planes broadcast 112-bit (long) or 56-bit (short) Mode S messages. The last 24 bits are a check code computed
 * with the generator 0x1FFF409. Feed a message in one bit at a time; when the last bit arrives the chip says whether
 * the check code matches, and lets you read back the plane's 24-bit ICAO address and the 24-bit syndrome.
 *
 * Inputs (ui_in)                 Outputs (uo_out)               Readout (uio_out, always driven)
 *   [0] DATA   message bit         [0] DONE  last bit received    VIEW=0: SEL 0 = first byte (format), 1..3 = ICAO address
 *   [1] STROBE rising edge = take  [1] OK    check code matches   VIEW=1: SEL 0 = bit count, 1..3 = syndrome bytes
 *   [2] START  rising edge = clear [2] BAD   check code fails
 *   [4:3] SEL  readout byte        [3] LONG  112-bit message
 *   [5] VIEW   readout source      [4] BUSY  part way through
 *
 * DATA, STROBE and START come from outside the chip at any time, so they pass through two flip-flops before use.
 * The first bit decides the length: formats 16 and up (first bit 1) are 112 bits, the rest are 56.
 */

`default_nettype none

module tt_um_raghavv711_hzn1_crc (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // always 1 when the design is powered, so you can ignore it
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

  localparam [23:0] POLY = 24'hFFF409;  // the Mode S generator 0x1FFF409 without its top bit

  // two-flop synchronisers, plus one more stage to find rising edges
  reg [2:0] s_data, s_stb, s_start;
  always @(posedge clk) begin
    if (!rst_n) begin
      s_data <= 3'b0; s_stb <= 3'b0; s_start <= 3'b0;
    end else begin
      s_data  <= {s_data[1:0],  ui_in[0]};
      s_stb   <= {s_stb[1:0],   ui_in[1]};
      s_start <= {s_start[1:0], ui_in[2]};
    end
  end
  wire bit_in  = s_data[1];
  wire take    = s_stb[1]   & ~s_stb[2];
  wire restart = s_start[1] & ~s_start[2];

  reg  [23:0] rem;    // running remainder; zero at the end means the check code matches
  reg  [6:0]  count;  // bits received so far
  reg         long_msg, done;
  reg  [31:0] head;   // first 32 bits: format byte and ICAO address

  wire        fb       = rem[23] ^ bit_in;
  wire        long_now = (count == 7'd0) ? bit_in : long_msg;
  wire [6:0]  last     = long_now ? 7'd111 : 7'd55;

  always @(posedge clk) begin
    if (!rst_n || restart) begin
      rem <= 24'd0; count <= 7'd0; long_msg <= 1'b0; done <= 1'b0; head <= 32'd0;
    end else if (take && !done) begin
      rem      <= {rem[22:0], 1'b0} ^ (fb ? POLY : 24'd0);
      long_msg <= long_now;
      if (count < 7'd32) head <= {head[30:0], bit_in};
      if (count == last) done <= 1'b1;
      count    <= count + 7'd1;
    end
  end

  wire ok = done && (rem == 24'd0);

  reg [7:0] readout;
  always @(*) begin
    case ({ui_in[5], ui_in[4:3]})
      3'b000: readout = head[31:24];
      3'b001: readout = head[23:16];
      3'b010: readout = head[15:8];
      3'b011: readout = head[7:0];
      3'b100: readout = {1'b0, count};
      3'b101: readout = rem[23:16];
      3'b110: readout = rem[15:8];
      default: readout = rem[7:0];
    endcase
  end

  assign uo_out  = {3'b000, (count != 7'd0) && !done, long_msg, done && !ok, ok, done};
  assign uio_out = readout;
  assign uio_oe  = 8'hFF;

  wire _unused = &{ena, uio_in, ui_in[7:6], 1'b0};

endmodule
