/* Testbench radio_core_log */

module tb_radio_core_log;
   timeunit 1ns;
   timeprecision 1fs;

   localparam width_dds    = 32;                  // DDS accumulator width
   localparam R1           = 250;                 // carrier to broad-band frequency ratio
   localparam R1a          = 5;                   // first CIC filter stage
   localparam R1b          = R1 / 5;              // second CIC filter stage
   localparam R2           = 30;                  // broad-band to audio frequency ratio
   localparam checks_goal  = 24;                  // integration checks to perform

   const realtime fdev = 75.0e3,                  // frequency deviation
                  tcm  = 1s / (100.0e6 + fdev),   // carrier frequency with frequency deviation
                  tc   = 1s / 100.0e6,            // unmodulated carrier clock
                  tclk = 1s / (R1 * R2 * 32.0e3); // sampling clock

   bit                           reset;        // reset
   bit                           clk;          // clock
   bit                           en1;          //  48 MHz first CIC filter clock enable
   bit                           en_b;         // 960 kHz base-band clock enable
   bit                           en_a;         //  32 kHz audio clock enable
   bit                           adc;          // broadcast signal from 1-bit ADC
   bit      [width_dds - 1:0]    K;            // phase constant for DDS
   wire signed [15:0]            demodulated;  // demodulated PCM audio
   wire     [7:0]                log_code;     // logarithmic audio code
   wire                          log_valid;    // code valid strobe
   reg [1:0]                     sample_history_valid;
   reg signed [15:0]             sample_d1;
   reg signed [15:0]             sample_d2;
   integer                       checks_done;

   radio_core_log dut(
      .reset      (reset),
      .clk        (clk),
      .en48m      (en1),
      .en960k     (en_b),
      .en32k      (en_a),
      .adc        (adc),
      .K          (K),
      .demodulated(demodulated),
      .log_code   (log_code),
      .log_valid  (log_valid));

   always #(tcm/2)  adc = ~adc;
   always #(tclk/2) clk = ~clk;

   always @(posedge clk)
     begin:clk_gen1
        int counter;

        if (reset)
          begin
             counter <= 0;
             en1     <= 1'b0;
          end
        else if (counter == R1a - 1)
          begin
             counter <= 0;
             en1     <= 1'b1;
          end
        else
          begin
             counter <= counter + 1;
             en1     <= 1'b0;
          end
     end:clk_gen1

   always @(posedge clk)
     begin:clk_gen2
        int counter;

        if (reset)
          begin
             counter <= 0;
             en_b    <= 1'b0;
          end
        else if (counter == R1a * R1b - 1)
          begin
             counter <= 0;
             en_b    <= 1'b1;
          end
        else
          begin
             counter <= counter + 1;
             en_b    <= 1'b0;
          end
     end:clk_gen2

   always @(posedge clk)
     begin:clk_gen3
        int counter;

        if (reset)
          begin
             counter <= 0;
             en_a    <= 1'b0;
          end
        else if (counter == R1 * R2 - 1)
          begin
             counter <= 0;
             en_a    <= 1'b1;
          end
        else
          begin
             counter <= counter + 1;
             en_a    <= 1'b0;
          end
     end:clk_gen3

   function automatic [7:0] reference_code
     (input logic signed [15:0] sample);
      int unsigned magnitude;
      int unsigned scaled;
      int unsigned lower_bound;
      int          segment;
      int          step;
      bit          sign;
      begin
         sign = sample[15];
         if (!sign)
           magnitude = sample;
         else if (sample == 16'sh8000)
           magnitude = 16'sh7fff;
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

   initial
     begin:main
        K = 2.0**32 * tclk / tc; // tune to carrier frequency

        reset = 1'b1;
        @(negedge clk);
        reset = 1'b0;

        #2ms;
        $fatal(1, "Timed out before completing radio_core_log checks");
     end:main

   initial
     begin:verify_path
        sample_history_valid = '0;
        sample_d1            = '0;
        sample_d2            = '0;
        checks_done          = 0;

        forever
          begin
             @(posedge clk);
             if (!reset && en_a)
               begin
                  #1ps;

                  if (sample_history_valid != 2'b11)
                    begin
                       if (log_valid !== 1'b0)
                         $fatal(1, "log_valid asserted before encoder pipeline was primed");
                    end
                  else
                    begin
                       if (log_valid !== 1'b1)
                         $fatal(1, "Missing log_valid pulse for demodulated sample %0d",
                                sample_d2);

                       if (log_code !== reference_code(sample_d2))
                         $fatal(1, "Unexpected log_code: pcm=%0d code=%0h expected=%0h",
                                sample_d2, log_code, reference_code(sample_d2));

                       checks_done = checks_done + 1;
                       if (checks_done == checks_goal)
                         $finish;
                    end

                  sample_d2            = sample_d1;
                  sample_d1            = demodulated;
                  sample_history_valid = {sample_history_valid[0], 1'b1};
               end
          end
     end:verify_path
endmodule
