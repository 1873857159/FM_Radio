/* Testbench log_encoder */

module tb_log_encoder;
   timeunit 1ns;
   timeprecision 1ps;

   localparam width_in = 16;
   const realtime tclk = 10ns;

   bit                              reset; // reset
   bit                              clk;   // clock
   bit                              en;    // clock enable
   bit signed [width_in - 1:0]      in;    // input sample
   wire [7:0]                       out;   // logarithmic output code

   log_encoder
     #(.width_in(width_in))
   dut(.*);

   always #(tclk/2) clk = ~clk;

   function automatic [7:0] reference_code
     (input logic signed [width_in - 1:0] sample);
      int unsigned magnitude;
      int unsigned scaled;
      int unsigned lower_bound;
      int          segment;
      int          step;
      bit          sign;
      begin
         sign = sample[width_in - 1];
         if (!sign)
           magnitude = sample;
         else if (sample == {1'b1, {(width_in - 1){1'b0}}})
           magnitude = (1 << (width_in - 1)) - 1;
         else
           magnitude = -sample;

         scaled = (magnitude + 4) >> 3;
         if (scaled > 4095)
           scaled = 4095;

         if (scaled == 0)
           reference_code = {sign, 7'h00};
         else
           begin
              segment = 0;
              while ((segment < 7)
                     && (scaled >= (16 * ((1 << (segment + 1)) - 1))))
                segment = segment + 1;

              lower_bound  = 16 * ((1 << segment) - 1);
              step         = (scaled - lower_bound) >> segment;
              if (step > 15)
                step = 15;

              reference_code = {sign, segment[2:0], step[3:0]};
           end
      end
   endfunction

   task automatic check_sample(input logic signed [width_in - 1:0] sample);
      reg [7:0] expected;
      begin
         expected = reference_code(sample);
         in <= sample;
         @(posedge clk);
         @(posedge clk);
         #1ps;
         if (out !== expected)
           $fatal(1, "Mismatch for sample=%0d out=%0h expected=%0h",
                  sample, out, expected);
      end
   endtask

   initial
     begin:main
        int sample;

        clk   = 1'b0;
        en    = 1'b0;
        in    = '0;
        reset = 1'b1;

        repeat (2) @(posedge clk);
        reset = 1'b0;
        en    = 1'b1;

        check_sample(16'sd0);
        check_sample(16'sd1);
        check_sample(-16'sd1);
        check_sample(16'sd127);
        check_sample(-16'sd127);
        check_sample(16'sd1024);
        check_sample(-16'sd1024);
        check_sample(16'sd32767);
        check_sample(-16'sd32768);

        for (sample = -32768; sample <= 32767; sample = sample + 257)
          check_sample(sample[width_in - 1:0]);

        $finish;
     end:main
endmodule
