/* EP4CE10F17C8 + PCM5102 three-wire top
 *
 * Audio path:
 *   tone_source_1k -> fm_modulator -> radio_core -> I2S(3-wire) -> PCM5102
 */

module ep4ce10_pcm5102_3wire_top
  (input  wire        clk240m,      // 240 MHz processing clock
   input  wire        reset_n,      // active-low reset
   output wire        pcm_bck,      // PCM5102 bit clock
   output wire        pcm_lrck,     // PCM5102 sample clock
   output wire        pcm_din,      // PCM5102 serial data
   output wire        fm_debug,     // on-chip FM waveform
   output wire [3:0]  led);         // debug LEDs

   wire               reset_in;
   wire               fm_out;
   wire               pwm_unused;
   wire               en32k_dbg;
   wire signed [15:0] audio_in_dbg;
   wire signed [15:0] audio_out_dbg;

   assign reset_in = ~reset_n;

   fm_loopback_ep4ce6_core inst_loopback
     (.reset_in     (reset_in),
      .clk240m      (clk240m),
      .fm_out       (fm_out),
      .pwm_out      (pwm_unused),
      .en32k_dbg    (en32k_dbg),
      .audio_in_dbg (audio_in_dbg),
      .audio_out_dbg(audio_out_dbg));

   i2s_tx_3wire inst_i2s_tx_3wire
     (.reset     (reset_in),
      .clk       (clk240m),
      .sample_stb(en32k_dbg),
      .sample    (audio_out_dbg),
      .bck       (pcm_bck),
      .lrck      (pcm_lrck),
      .din       (pcm_din));

   assign fm_debug = fm_out;
   assign led[0]   = reset_n;
   assign led[1]   = pcm_lrck;
   assign led[2]   = pcm_bck;
   assign led[3]   = audio_out_dbg[$left(audio_out_dbg)];
endmodule
