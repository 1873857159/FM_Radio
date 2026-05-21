module tb_cic_3_filter;
   timeunit 1ns;
   timeprecision 1ps;

   localparam R     = 5; // decimation ratio
   localparam width = 2; // input data width

   const realtime tclk = 1s/250e6;

   bit                                        reset;         // reset
   bit                                        clk;           // clock
   const bit                                  en_in = 1'b1;  // clock enable input
   bit                                        en_out;        // clock enable output
   bit  signed [width - 1 : 0]                in;            // input
   wire signed [width + $clog2(R**3) - 1 : 0] out;           // filtered and decimated outpu

   cic_3_filter
     #(.R    (R),
       .width(width))
   dut(.*);

   always #(tclk/2)  clk  = ~clk;

   always @(posedge clk)
     begin:clk_gen
        int counter;

        if (reset)
          begin
             counter <= 0;
             en_out  <= 1'b0;
          end
        else if (counter == R - 1)
          begin
             counter <= 0;
             en_out  <= 1'b1;
          end
        else
          begin
             counter <= counter + 1;
             en_out  <= 1'b0;
          end
     end:clk_gen

   task automatic wait_decimated_samples(input int count);
      repeat (count)
        begin
           @(posedge clk);
           while (!en_out)
             @(posedge clk);
           #1ps;
        end
   endtask

   task automatic check_dc_gain(input signed [width - 1 : 0] sample);
      in <= sample;

      // A 3rd-order CIC settles after a few decimated output samples.
      wait_decimated_samples(8);
      assert (out == R**3 * sample)
        else $error("Unexpected CIC output: in=%0d out=%0d expected=%0d",
                    sample, out, R**3 * sample);

      // Check that the output remains stable for a couple more samples.
      wait_decimated_samples(2);
      assert (out == R**3 * sample)
        else $error("CIC output did not remain stable: in=%0d out=%0d expected=%0d",
                    sample, out, R**3 * sample);
   endtask

   initial
     begin:main
        clk    = 1'b0;
        en_out = 1'b0;
        in     = '0;
        reset = 1'b1;
        @(negedge clk);
        reset = 1'b0;

        check_dc_gain(1);
        check_dc_gain(-1);
        check_dc_gain(0);

        $finish;
     end:main
endmodule
