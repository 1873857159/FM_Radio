/* Lightweight 1 kHz sine source
 *
 * This ROM-based tone source is intended for small FPGA devices where the
 * original test_tone CORDIC generator is too expensive. The waveform is
 * updated at the 32 kHz audio sample rate.
 */

module tone_source_1k
  (input  wire               reset, // reset
   input  wire               clk,   // clock
   input  wire               en,    // clock enable (32 kHz)
   output logic signed [15:0] data); // audio data

   logic [4:0] phase;

   always_ff @(posedge clk or posedge reset)
     if (reset)
       phase <= '0;
     else if (en)
       phase <= phase + 1'b1;

   always_comb
     case (phase)
       5'd0  : data = 16'sd0;
       5'd1  : data = 16'sd3196;
       5'd2  : data = 16'sd6270;
       5'd3  : data = 16'sd9102;
       5'd4  : data = 16'sd11585;
       5'd5  : data = 16'sd13623;
       5'd6  : data = 16'sd15137;
       5'd7  : data = 16'sd16069;
       5'd8  : data = 16'sd16384;
       5'd9  : data = 16'sd16069;
       5'd10 : data = 16'sd15137;
       5'd11 : data = 16'sd13623;
       5'd12 : data = 16'sd11585;
       5'd13 : data = 16'sd9102;
       5'd14 : data = 16'sd6270;
       5'd15 : data = 16'sd3196;
       5'd16 : data = 16'sd0;
       5'd17 : data = -16'sd3196;
       5'd18 : data = -16'sd6270;
       5'd19 : data = -16'sd9102;
       5'd20 : data = -16'sd11585;
       5'd21 : data = -16'sd13623;
       5'd22 : data = -16'sd15137;
       5'd23 : data = -16'sd16069;
       5'd24 : data = -16'sd16384;
       5'd25 : data = -16'sd16069;
       5'd26 : data = -16'sd15137;
       5'd27 : data = -16'sd13623;
       5'd28 : data = -16'sd11585;
       5'd29 : data = -16'sd9102;
       5'd30 : data = -16'sd6270;
       default: data = -16'sd3196;
     endcase
endmodule
