/* Minimal EP4CE6 -> PCM5102 top level
 *
 * Required clocks:
 * - clk240m   : radio-core processing clock
 * - clk12m288 : audio serial clock for I2S generation
 *
 * Audio path:
 *   tone_source_1k -> fm_modulator -> radio_core -> I2S -> PCM5102
 */

module ep4ce6_pcm5102_top
  (input  wire        clk240m,      // 240 MHz processing clock
   input  wire        clk12m288,    // 12.288 MHz audio clock
   input  wire        reset_n,      // active-low reset
   output wire        pcm_sck,      // PCM5102 system clock
   output wire        pcm_bck,      // PCM5102 BCK
   output wire        pcm_lrck,     // PCM5102 LRCK
   output wire        pcm_din,      // PCM5102 DIN
   output wire        fm_debug,     // on-chip FM waveform
   output wire [3:0]  led);         // debug LEDs

   wire               reset_in;
   wire               fm_out;
   wire               pwm_unused;
   wire               en32k_dbg;
   wire signed [15:0] audio_in_dbg;
   wire signed [15:0] audio_out_dbg;
   wire               i2s_sample_stb;
   wire signed [15:0] i2s_sample;

   assign reset_in = ~reset_n;

   fm_loopback_ep4ce6_core inst_loopback
     (.reset_in     (reset_in),
      .clk240m      (clk240m),
      .fm_out       (fm_out),
      .pwm_out      (pwm_unused),
      .en32k_dbg    (en32k_dbg),
      .audio_in_dbg (audio_in_dbg),
      .audio_out_dbg(audio_out_dbg));

   audio_sample_bridge inst_sample_bridge
     (.reset     (reset_in),
      .src_clk   (clk240m),
      .src_stb   (en32k_dbg),
      .src_sample(audio_out_dbg),
      .dst_clk   (clk12m288),
      .dst_stb   (i2s_sample_stb),
      .dst_sample(i2s_sample));

   i2s_tx inst_i2s_tx
     (.reset     (reset_in),
      .clk       (clk12m288),
      .sample_stb(i2s_sample_stb),
      .sample    (i2s_sample),
      .bck       (pcm_bck),
      .lrck      (pcm_lrck),
      .din       (pcm_din));

   assign fm_debug = fm_out;
   assign pcm_sck  = clk12m288;
   assign led[0]   = reset_n;
   assign led[1]   = pcm_lrck;
   assign led[2]   = pcm_bck;
   assign led[3]   = audio_out_dbg[$left(audio_out_dbg)];
endmodule
