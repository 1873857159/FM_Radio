/* Testbench i2s_tx_3wire
 *
 * Checks I2S framing for the three-wire transmitter that derives BCK/LRCK
 * internally from the 240 MHz system clock.
 */

module tb_i2s_tx_3wire;
   timeunit 1ns;
   timeprecision 1fs;

   const realtime tclk = 1s / 240.0e6;

   bit               reset;
   bit               clk;
   bit               sample_stb;
   bit signed [15:0] sample;
   wire              bck;
   wire              lrck;
   wire              din;

   logic [31:0]      left_slot;
   logic [31:0]      right_slot;
   integer           left_count;
   integer           right_count;

   i2s_tx_3wire dut
     (.reset,
      .clk,
      .sample_stb,
      .sample,
      .bck,
      .lrck,
      .din);

   always #(tclk/2.0) clk = ~clk;

   always @(posedge bck or posedge reset)
     if (reset)
       begin
          left_slot   <= '0;
          right_slot  <= '0;
          left_count  <= 0;
          right_count <= 0;
       end
     else if (!lrck)
       begin
          left_slot  <= {left_slot[30:0], din};
          left_count <= left_count + 1;
       end
     else
       begin
          right_slot  <= {right_slot[30:0], din};
          right_count <= right_count + 1;
       end

   initial
     begin
        clk        = 1'b0;
        reset      = 1'b1;
        sample_stb = 1'b0;
        sample     = 16'sh5A3C;

        repeat (16) @(negedge clk);
        reset = 1'b0;

        @(negedge clk);
        sample_stb = 1'b1;
        @(negedge clk);
        sample_stb = 1'b0;

        wait (left_count >= 128);
        wait (right_count >= 128);

        if (left_slot !== {1'b0, 16'h5A3C, 15'b0})
          $fatal(1, "Unexpected left slot: %h", left_slot);

        if (right_slot !== {1'b0, 16'h5A3C, 15'b0})
          $fatal(1, "Unexpected right slot: %h", right_slot);

        $display("Three-wire I2S frame check passed: left=%h right=%h", left_slot, right_slot);
        $finish;
     end

   initial
     begin
        #400us;
        $fatal(1, "Timed out before three-wire I2S frame completed");
     end
endmodule
