/* Testbench fm_loopback_audio_rom_dump
 *
 * Exports a short aligned sample window from the ROM-audio FM loopback path:
 * audio_rom_source -> fm_modulator -> radio_core -> pwm_audio
 *
 * The dump file is intended for offline waveform / spectrum / spectrogram
 * analysis in the analysis/audio_compare toolchain.
 */

module tb_fm_loopback_audio_rom_dump;
   timeunit 1ns;
   timeprecision 1fs;

`ifdef TB_WARMUP_SAMPLES
   localparam int  warmup_samples  = `TB_WARMUP_SAMPLES;
`else
   localparam int  warmup_samples  = 320;
`endif
`ifdef TB_CAPTURE_SAMPLES
   localparam int  capture_samples = `TB_CAPTURE_SAMPLES;
`else
   localparam int  capture_samples = 1024;
`endif
`ifdef TB_AUDIO_START_ADDR
   localparam int  start_addr      = `TB_AUDIO_START_ADDR;
`else
   localparam int  start_addr      = 4096;
`endif
   const realtime tclk             = 1s / 240.0e6;

   bit                reset_in;
   bit                clk240m;
   wire               fm_out;
   wire               pwm_out;
   wire               en32k_dbg;
   wire signed [15:0] audio_in_dbg;
   wire signed [15:0] audio_out_dbg;
   integer            sample_count;
   integer            capture_index;
   integer            dump_fd;

   fm_loopback_audio_rom_core
     #(.audio_start_addr(start_addr))
   dut
     (.reset_in,
      .clk240m,
      .clk_audio_src(clk240m),
      .fm_out,
      .pwm_out,
      .en32k_dbg,
      .audio_in_dbg,
      .audio_out_dbg);

   always #(tclk/2.0) clk240m = ~clk240m;

   initial
     begin
        clk240m      = 1'b0;
        reset_in     = 1'b1;
        sample_count = 0;
        capture_index = 0;
        dump_fd = $fopen("outputs/fm_loopback_audio_rom_dump_samples.txt", "w");
        if (dump_fd == 0)
          $fatal(1, "Failed to open dump output file");

        $fwrite(dump_fd, "# index source output\n");

        repeat (8) @(negedge clk240m);
        reset_in = 1'b0;
     end

   initial
     begin:dump_samples
        forever
          begin
             @(posedge clk240m);
             if (!reset_in && en32k_dbg)
               begin
                  if (sample_count >= warmup_samples)
                    begin
                       $fwrite(dump_fd, "%0d %0d %0d\n",
                               capture_index, audio_in_dbg, audio_out_dbg);
                       capture_index = capture_index + 1;

                       if (capture_index == capture_samples)
                         begin
                            $fclose(dump_fd);
                            $display("Dumped %0d audio samples for offline analysis",
                                     capture_samples);
                            $finish;
                         end
                    end

                  sample_count = sample_count + 1;
               end
          end
     end:dump_samples

   initial
     begin:timeout_guard
        #180ms;
        if (dump_fd != 0)
          $fclose(dump_fd);
        $fatal(1, "Timed out before completing fm_loopback_audio_rom_dump");
     end:timeout_guard
endmodule
