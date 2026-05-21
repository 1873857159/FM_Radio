/* Testbench fm_loopback_ep4ce6
 *
 * Verifies the lightweight on-chip loopback path:
 * tone_source_1k -> fm_modulator -> radio_core -> pwm_audio
 */

module tb_fm_loopback_ep4ce6;
   timeunit 1ns;
   timeprecision 1fs;

   localparam int  capture_samples = 128;              // samples used for analysis
   localparam real pi              = 3.14159265358979323846;
   localparam real two_pi          = 2.0 * pi;
   const realtime tclk             = 1s / 240.0e6;

   bit                       reset_in;
   bit                       clk240m;
   wire                      fm_out;
   wire                      pwm_out;
   wire                      en32k_dbg;
   wire signed [15:0]        audio_in_dbg;
   wire signed [15:0]        audio_out_dbg;
   integer                   sample_count;
   integer                   pwm_edges;
   integer                   index;
   bit                       pwm_prev;
   integer signed            source_capture[capture_samples];
   integer signed            sink_capture[capture_samples];

   fm_loopback_ep4ce6_core dut
     (.reset_in,
      .clk240m,
      .fm_out,
      .pwm_out,
      .en32k_dbg,
      .audio_in_dbg,
      .audio_out_dbg);

   always #(tclk/2.0) clk240m = ~clk240m;

   always @(posedge clk240m)
     begin
        if (reset_in)
          begin
             pwm_prev  <= 1'b0;
             pwm_edges <= 0;
          end
        else
          begin
             if (pwm_out !== pwm_prev)
               pwm_edges <= pwm_edges + 1;
             pwm_prev <= pwm_out;
          end
     end

   task automatic analyze_correlation;
      integer i;
      real mean_y;
      real energy_y;
      real sin_acc;
      real cos_acc;
      real sample_y;
      real coherence_1k;
      begin
         mean_y = 0.0;
         for (i = 0; i < capture_samples; i = i + 1)
           mean_y = mean_y + sink_capture[i];

         mean_y = mean_y / capture_samples;
         energy_y = 0.0;
         sin_acc  = 0.0;
         cos_acc  = 0.0;

         for (i = 0; i < capture_samples; i = i + 1)
           begin
              sample_y = sink_capture[i] - mean_y;
              energy_y = energy_y + sample_y * sample_y;
              sin_acc  = sin_acc + sample_y * $sin(two_pi * i / 32.0);
              cos_acc  = cos_acc + sample_y * $cos(two_pi * i / 32.0);
           end

         if (energy_y <= 1.0)
           $fatal(1, "Loopback output energy is too small: sink=%f", energy_y);

         coherence_1k = $sqrt(sin_acc * sin_acc + cos_acc * cos_acc)
                      / $sqrt(energy_y * (capture_samples / 2.0));
         $display("FM EP4CE6 loopback coherence_1k=%0.4f pwm_edges=%0d",
                  coherence_1k, pwm_edges);

         if (coherence_1k < 0.90)
           $fatal(1, "Recovered 1 kHz component is too weak: %0.4f",
                  coherence_1k);

         if (pwm_edges < 1000)
           $fatal(1, "PWM output does not toggle often enough: %0d", pwm_edges);
      end
   endtask

   initial
     begin
        clk240m      = 1'b0;
        reset_in     = 1'b1;
        sample_count = 0;
        index        = 0;
        pwm_prev     = 1'b0;

        repeat (8) @(negedge clk240m);
        reset_in = 1'b0;
     end

   initial
     begin:collect_samples
        forever
          begin
             @(posedge clk240m);
             if (!reset_in && en32k_dbg)
               begin
                  if (sample_count >= 128)
                    begin
                       source_capture[index] = audio_in_dbg;
                       sink_capture[index]   = audio_out_dbg;
                       index = index + 1;

                       if (index == capture_samples)
                         begin
                            analyze_correlation();
                            $finish;
                         end
                    end

                  sample_count = sample_count + 1;
               end
          end
     end:collect_samples

   initial
     begin:timeout_guard
        #12ms;
        $fatal(1, "Timed out before completing fm_loopback_ep4ce6 checks");
     end:timeout_guard
endmodule
