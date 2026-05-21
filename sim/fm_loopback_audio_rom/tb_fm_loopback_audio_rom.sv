/* Testbench fm_loopback_audio_rom
 *
 * Verifies the ROM-audio loopback path:
 * audio_rom_source -> fm_modulator -> radio_core -> pwm_audio
 */

module tb_fm_loopback_audio_rom;
   timeunit 1ns;
   timeprecision 1fs;

   localparam int  warmup_samples  = 2000;
   localparam int  capture_samples = 128;
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

   fm_loopback_audio_rom_core dut
     (.reset_in,
      .clk240m,
      .clk_audio_src(clk240m),
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

   task automatic analyze_clip;
      integer i;
      integer lag;
      integer overlap;
      real src_mean;
      real sink_mean;
      real src_energy;
      real sink_energy;
      real cov;
      real corr;
      real best_corr;
      real abs_corr;
      integer src_min;
      integer src_max;
      begin
         src_mean = 0.0;
         sink_mean = 0.0;
         src_min = source_capture[0];
         src_max = source_capture[0];

         for (i = 0; i < capture_samples; i = i + 1)
           begin
              src_mean = src_mean + source_capture[i];
              sink_mean = sink_mean + sink_capture[i];
              if (source_capture[i] < src_min)
                src_min = source_capture[i];
              if (source_capture[i] > src_max)
                src_max = source_capture[i];
           end

         src_mean = src_mean / capture_samples;
         sink_mean = sink_mean / capture_samples;
         src_energy = 0.0;
         sink_energy = 0.0;
         for (i = 0; i < capture_samples; i = i + 1)
           begin
              src_energy = src_energy + (source_capture[i] - src_mean) * (source_capture[i] - src_mean);
              sink_energy = sink_energy + (sink_capture[i] - sink_mean) * (sink_capture[i] - sink_mean);
           end

         if ((src_max - src_min) < 12000)
           $fatal(1, "Audio ROM source span is too small: %0d", src_max - src_min);

         if (sink_energy < 1.0e8)
           $fatal(1, "Recovered clip energy is too small: %f", sink_energy);

         best_corr = 0.0;
         for (lag = 0; lag <= 24; lag = lag + 1)
           begin
              overlap = capture_samples - lag;
              cov = 0.0;
              src_energy = 0.0;
              sink_energy = 0.0;
              for (i = 0; i < overlap; i = i + 1)
                begin
                   cov = cov
                       + (source_capture[i] - src_mean)
                       * (sink_capture[i + lag] - sink_mean);
                   src_energy = src_energy
                              + (source_capture[i] - src_mean)
                              * (source_capture[i] - src_mean);
                   sink_energy = sink_energy
                               + (sink_capture[i + lag] - sink_mean)
                               * (sink_capture[i + lag] - sink_mean);
                end

              if ((src_energy > 0.0) && (sink_energy > 0.0))
                begin
                   corr = cov / $sqrt(src_energy * sink_energy);
                   if (corr < 0.0)
                     abs_corr = -corr;
                   else
                     abs_corr = corr;

                   if (abs_corr > best_corr)
                     best_corr = abs_corr;
                end
           end

         $display("FM audio ROM loopback best_abs_corr=%0.4f pwm_edges=%0d",
                  best_corr, pwm_edges);

         if (best_corr < 0.20)
           $fatal(1, "Recovered clip correlation is too weak: %0.4f", best_corr);

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
                  if (sample_count >= warmup_samples)
                    begin
                       source_capture[index] = audio_in_dbg;
                       sink_capture[index]   = audio_out_dbg;
                       index = index + 1;

                       if (index == capture_samples)
                         begin
                            analyze_clip();
                            $finish;
                         end
                    end

                  sample_count = sample_count + 1;
               end
          end
     end:collect_samples

   initial
     begin:timeout_guard
        #120ms;
        $fatal(1, "Timed out before completing fm_loopback_audio_rom checks");
     end:timeout_guard
endmodule
