/* EP4CE10F17C8 minimum LED diagnostic top
 *
 * This image only verifies the on-board 50 MHz clock, reset input and LED
 * pin mapping. DS0 shows the raw reset level, while DS1..DS3 blink at
 * different slow rates so the user can confirm the clock is alive by eye
 * regardless of LED polarity.
 */

module ep4ce10_diag_led_50m_top
  (input  wire       clk50m,   // on-board 50 MHz clock
   input  wire       reset_n,  // active-low reset
   output wire       fm_debug, // spare debug pin
   output logic [3:0] led);    // debug LEDs

   logic [26:0] counter;

   always_ff @(posedge clk50m)
     counter <= counter + 1'b1;

   always_comb
     begin
        led[0] = reset_n;
        led[1] = counter[23];
        led[2] = counter[24];
        led[3] = counter[25];
     end

   assign fm_debug = counter[23];
endmodule
