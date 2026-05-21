/* EP4CE10F17C8 + PCM5102 three-wire top for common 50 MHz core boards */

module ep4ce10_pcm5102_3wire_50m_top
  (input  wire        clk50m,       // on-board 50 MHz clock
   input  wire        reset_n,      // active-low reset
   output wire        pcm_bck,      // PCM5102 bit clock
   output wire        pcm_lrck,     // PCM5102 sample clock
   output wire        pcm_din,      // PCM5102 serial data
   output wire        fm_debug,     // on-chip FM debug waveform
   output wire [3:0]  led);         // debug LEDs

   wire pll_locked;
   wire clk240m;

   pll_50m_to_240m inst_pll_50m_to_240m
     (.inclk0(clk50m),
      .c0    (clk240m),
      .locked(pll_locked));

   ep4ce10_pcm5102_3wire_top inst_pcm5102_top
     (.clk240m (clk240m),
      .reset_n (reset_n & pll_locked),
      .pcm_bck,
      .pcm_lrck,
      .pcm_din,
      .fm_debug,
      .led);
endmodule
