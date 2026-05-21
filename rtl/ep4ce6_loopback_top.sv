/* Minimal EP4CE6 core-board top level
 *
 * This top level is intended for a bare EP4CE6F17C8 core board.
 * It keeps only the on-chip FM loopback path and a few debug outputs:
 *
 *   tone_source_1k -> fm_modulator -> radio_core -> pwm_audio
 *
 * External requirements:
 * - 240 MHz system clock on clk240m
 * - RC low-pass filter plus active speaker/amp on pwm_audio
 */

module ep4ce6_loopback_top
  (input  wire        clk240m,    // 240 MHz input clock
   input  wire        reset_n,    // active-low reset
   output wire        pwm_audio,  // PWM audio output
   output wire        fm_debug,   // synthesized 1-bit FM waveform
   output wire [3:0]  led);       // basic debug LEDs

   wire               reset_in;
   wire               fm_out;
   wire               pwm_out;
   wire signed [15:0] audio_out_dbg;

   fm_loopback_ep4ce6_core inst_loopback
     (.reset_in     (reset_in),
      .clk240m      (clk240m),
      .fm_out       (fm_out),
      .pwm_out      (pwm_out),
      .audio_out_dbg(audio_out_dbg));

   assign reset_in  = ~reset_n;
   assign pwm_audio = pwm_out;
   assign fm_debug  = fm_out;

   assign led[0] = reset_n;
   assign led[1] = pwm_out;
   assign led[2] = fm_out;
   assign led[3] = audio_out_dbg[$left(audio_out_dbg)];
endmodule
