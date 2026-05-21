/* EP4CE10F17C8 static output diagnostic top
 *
 * This image does not depend on the on-board clock. It simply drives the
 * user LEDs and the spare debug pin high so the board pin mapping can be
 * checked independently of the oscillator path.
 */

module ep4ce10_diag_static_top
  (input  wire       reset_n,  // unused, kept for board-level consistency
   output wire       fm_debug, // spare debug pin / buzzer pin on some boards
   output wire [3:0] led);     // debug LEDs

   assign led      = 4'b1111;
   assign fm_debug = 1'b1;

endmodule
