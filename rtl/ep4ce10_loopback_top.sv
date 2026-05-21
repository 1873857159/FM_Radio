/* EP4CE10F17C8 wrapper for the lightweight loopback top
 *
 * This keeps the top-level entity name aligned with the target core board
 * while reusing the already-verified small-device implementation.
 */

module ep4ce10_loopback_top
  (input  wire       clk240m,    // 240 MHz processing clock
   input  wire       reset_n,    // active-low reset
   output wire       pwm_audio,  // PWM audio output
   output wire       fm_debug,   // on-chip FM waveform
   output wire [3:0] led);       // debug LEDs

   ep4ce6_loopback_top inst_ep4ce6_loopback_top
     (.clk240m,
      .reset_n,
      .pwm_audio,
      .fm_debug,
      .led);
endmodule
