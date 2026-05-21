/* EP4CE10F17C8 wrapper for the PCM5102 audio top
 *
 * The logic stays identical to the verified EP4CE6-class version; only the
 * top-level entity name is normalized for the EP4CE10 core-board package.
 */

module ep4ce10_pcm5102_top
  (input  wire        clk240m,      // 240 MHz processing clock
   input  wire        clk12m288,    // 12.288 MHz audio clock
   input  wire        reset_n,      // active-low reset
   output wire        pcm_sck,      // PCM5102 system clock
   output wire        pcm_bck,      // PCM5102 bit clock
   output wire        pcm_lrck,     // PCM5102 sample clock
   output wire        pcm_din,      // PCM5102 serial data
   output wire        fm_debug,     // on-chip FM waveform
   output wire [3:0]  led);         // debug LEDs

   ep4ce6_pcm5102_top inst_ep4ce6_pcm5102_top
     (.clk240m,
      .clk12m288,
      .reset_n,
      .pcm_sck,
      .pcm_bck,
      .pcm_lrck,
      .pcm_din,
      .fm_debug,
      .led);
endmodule
