/* Testbench radio_core_audio_dump
 *
 * Drives the normal 32 kHz PCM -> fm_modulator -> radio_core path with a
 * single-tone sine wave and dumps a steady-state audio window for offline
 * frequency-response analysis.
 */

module tb_radio_core_audio_dump;
   timeunit 1ns;
   timeprecision 1fs;

   localparam int  width_dds       = 32;                 // DDS accumulator width
   localparam int  width_cordic    = 17;                 // CORDIC width
   localparam int  R1              = 250;                // carrier to broad-band frequency ratio
   localparam int  R1a             = 5;                  // first CIC filter stage
   localparam int  R1b             = R1 / 5;             // second CIC filter stage
   localparam int  R2              = 30;                 // broad-band to audio frequency ratio
   localparam int  audio_fs_hz     = 32_000;             // output audio sample rate
`ifdef TB_REFERENCE_PEAK
   localparam int  reference_peak  = `TB_REFERENCE_PEAK; // reference dump amplitude
`else
   localparam int  reference_peak  = 16'sd8192;          // default to a linear-range tone
`endif

`ifdef TB_TONE_HZ
   localparam int  tone_hz         = `TB_TONE_HZ;
`else
   localparam int  tone_hz         = 1_000;
`endif
`ifdef TB_SETTLE_SAMPLES
   localparam int  settle_samples  = `TB_SETTLE_SAMPLES;
`else
   localparam int  settle_samples  = 256;
`endif
`ifdef TB_CAPTURE_SAMPLES
   localparam int  capture_samples = `TB_CAPTURE_SAMPLES;
`else
   localparam int  capture_samples = 1024;
`endif

   localparam real pi              = 3.14159265358979323846;
   localparam real two_pi          = 2.0 * pi;
   localparam real clk_hz          = R1 * R2 * audio_fs_hz;
   localparam real carrier_hz      = 100.0e6;
   localparam real tone_step       = two_pi * tone_hz / audio_fs_hz;
   const realtime tclk             = 1s / clk_hz;

   bit                           reset;
   bit                           clk;
   bit                           en1;
   bit                           en_b;
   bit                           en_a;
   bit      [width_dds - 1:0]    K;
   logic signed [15:0]           audio_in;
   wire                          fm_out;
   wire signed [15:0]            demodulated;

   real                          tone_phase;
   integer                       audio_samples_seen;
   integer                       capture_index;
   integer                       dump_fd;

   fm_modulator
     #(.width_phase(width_dds),
       .width_audio($bits(audio_in)))
   inst_fm_modulator
     (.reset,
      .clk,
      .en_audio (en_a),
      .K_carrier(K),
      .audio_in,
      .fm_out);

   radio_core
     #(.width_dds   (width_dds),
       .width_cordic(width_cordic),
       .R1          (R1),
       .R2          (R2))
   dut
     (.reset,
      .clk,
      .en48m      (en1),
      .en960k     (en_b),
      .en32k      (en_a),
      .adc        (fm_out),
      .K,
      .demodulated);

   always #(tclk/2.0) clk = ~clk;

   always @(posedge clk)
     begin:audio_source
        real next_phase;

        if (reset)
          begin
             tone_phase = 0.0;
             audio_in   <= '0;
          end
        else if (en_a)
          begin
             next_phase = tone_phase + tone_step;
             if (next_phase >= two_pi)
               next_phase = next_phase - two_pi;

             tone_phase = next_phase;
             audio_in   <= $rtoi(reference_peak * $sin(next_phase));
          end
     end:audio_source

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

   initial
     begin:main
        K = int'($rtoi((2.0**width_dds) * carrier_hz / clk_hz));

        clk                = 1'b0;
        reset              = 1'b1;
        en1                = 1'b0;
        en_b               = 1'b0;
        en_a               = 1'b0;
        audio_in           = '0;
        tone_phase         = 0.0;
        audio_samples_seen = 0;
        capture_index      = 0;
        dump_fd            = $fopen("outputs/radio_core_audio_dump_samples.txt", "w");

        if (dump_fd == 0)
          $fatal(1, "Failed to open radio_core_audio_dump_samples.txt");

        $fwrite(dump_fd, "# index source output\n");

        @(negedge clk);
        reset = 1'b0;
     end:main

   initial
     begin:dump_audio
        forever
          begin
             @(posedge clk);
             if (!reset && en_a)
               begin
                  #1ps;

                  if (audio_samples_seen >= settle_samples)
                    begin
                       $fwrite(dump_fd, "%0d %0d %0d\n",
                               capture_index, audio_in, demodulated);
                       capture_index = capture_index + 1;

                       if (capture_index == capture_samples)
                         begin
                            $fclose(dump_fd);
                            $display("Dumped %0d audio samples at %0d Hz for offline analysis",
                                     capture_samples, tone_hz);
                            $finish;
                         end
                    end

                  audio_samples_seen = audio_samples_seen + 1;
               end
          end
     end:dump_audio

   initial
     begin:timeout_guard
        #80ms;
        if (dump_fd != 0)
          $fclose(dump_fd);
        $fatal(1, "Timed out before completing radio_core_audio_dump");
     end:timeout_guard
endmodule
