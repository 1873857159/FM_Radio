/* Testbench radio_core_audio
 *
 * This testbench injects a 1-bit FM waveform with a 1 kHz sinusoidal
 * modulation into radio_core and checks whether the demodulated 32 kHz
 * audio stream still contains a strong 1 kHz component.
 */

module tb_radio_core_audio;
   timeunit 1ns;
   timeprecision 1fs;

   localparam int  width_dds      = 32;                  // DDS accumulator width
   localparam int  width_cordic   = 17;                  // CORDIC width
   localparam int  R1             = 250;                 // carrier to broad-band frequency ratio
   localparam int  R1a            = 5;                   // first CIC filter stage
   localparam int  R1b            = R1 / 5;              // second CIC filter stage
   localparam int  R2             = 30;                  // broad-band to audio frequency ratio
   localparam int  audio_fs_hz    = 32_000;              // audio sampling rate
   localparam int  tone_hz        = 1_000;               // FM modulation tone
   localparam int  settle_samples = 128;                 // audio samples discarded for settling
   localparam int  capture_samples = 128;                // audio samples used for analysis

   localparam real pi             = 3.14159265358979323846;
   localparam real two_pi         = 2.0 * pi;
   localparam real clk_hz         = R1 * R2 * audio_fs_hz;
   localparam real carrier_hz     = 100.0e6;
   localparam real deviation_hz   = 75.0e3;
   localparam real tone_step      = two_pi * tone_hz / audio_fs_hz;
   const realtime tclk            = 1s / clk_hz;

   bit                           reset;                  // reset
   bit                           clk;                    // clock
   bit                           en1;                    //  48 MHz first CIC filter clock enable
   bit                           en_b;                   // 960 kHz base-band clock enable
   bit                           en_a;                   //  32 kHz audio clock enable
   bit                           adc;                    // broadcast signal from 1-bit ADC
   bit      [width_dds - 1:0]    K;                      // phase constant for DDS
   wire signed [15:0]            demodulated;            // demodulated PCM audio

   real                          carrier_phase;          // carrier phase in radians
   real                          tone_phase;             // modulation phase in radians
   integer                       audio_samples_seen;     // total audio samples after reset
   integer                       captured_count;         // captured samples for analysis
   integer signed                captured[capture_samples];

   radio_core
     #(.width_dds   (width_dds),
       .width_cordic(width_cordic),
       .R1          (R1),
       .R2          (R2))
   dut(
      .reset      (reset),
      .clk        (clk),
      .en48m      (en1),
      .en960k     (en_b),
      .en32k      (en_a),
      .adc        (adc),
      .K          (K),
      .demodulated(demodulated));

   always #(tclk/2.0) clk = ~clk;

   always @(negedge clk)
     begin:fm_source
        real inst_freq;

        if (reset)
          begin
             tone_phase    = 0.0;
             carrier_phase = 0.0;
             adc           <= 1'b0;
          end
        else
          begin
             tone_phase = tone_phase + (two_pi * tone_hz / clk_hz);
             if (tone_phase >= two_pi)
               tone_phase = tone_phase - two_pi;

             inst_freq = carrier_hz + deviation_hz * $sin(tone_phase);

             carrier_phase = carrier_phase + (two_pi * inst_freq / clk_hz);
             if (carrier_phase >= two_pi)
               carrier_phase = carrier_phase - two_pi;

             adc <= (carrier_phase < pi);
          end
     end:fm_source

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

   task automatic analyze_capture;
      integer i;
      integer peak_abs;
      integer abs_sample;
      real    mean_value;
      real    sample_value;
      real    energy;
      real    sin_acc;
      real    cos_acc;
      real    coherence_1k;
      begin
         mean_value = 0.0;
         peak_abs   = 0;
         for (i = 0; i < capture_samples; i = i + 1)
           begin
              mean_value = mean_value + captured[i];
              abs_sample = (captured[i] < 0) ? -captured[i] : captured[i];
              if (abs_sample > peak_abs)
                peak_abs = abs_sample;
           end

         mean_value = mean_value / capture_samples;
         energy     = 0.0;
         sin_acc    = 0.0;
         cos_acc    = 0.0;

         for (i = 0; i < capture_samples; i = i + 1)
           begin
              sample_value = captured[i] - mean_value;
              energy = energy + sample_value * sample_value;
              sin_acc = sin_acc + sample_value * $sin(tone_step * i);
              cos_acc = cos_acc + sample_value * $cos(tone_step * i);
           end

         if (energy <= 1.0)
           $fatal(1, "Demodulated audio energy is too small: %f", energy);

         coherence_1k = $sqrt(sin_acc * sin_acc + cos_acc * cos_acc)
                       / $sqrt(energy * (capture_samples / 2.0));

         $display("FM audio check: mean=%0.2f peak=%0d coherence_1k=%0.4f",
                  mean_value, peak_abs, coherence_1k);

         if (peak_abs < 32)
           $fatal(1, "Demodulated audio peak is too small: %0d", peak_abs);

         if (coherence_1k < 0.75)
           $fatal(1, "1 kHz component is too weak: coherence=%0.4f", coherence_1k);
      end
   endtask

   initial
     begin:main
        K = int'($rtoi((2.0**width_dds) * carrier_hz / clk_hz));

        clk                = 1'b0;
        adc                = 1'b0;
        reset              = 1'b1;
        en1                = 1'b0;
        en_b               = 1'b0;
        en_a               = 1'b0;
        carrier_phase      = 0.0;
        tone_phase         = 0.0;
        audio_samples_seen = 0;
        captured_count     = 0;

        @(negedge clk);
        reset = 1'b0;

        #12ms;
        $fatal(1, "Timed out before completing FM audio recovery checks");
     end:main

   initial
     begin:verify_audio
        forever
          begin
             @(posedge clk);
             if (!reset && en_a)
               begin
                  #1ps;

                  if (audio_samples_seen >= settle_samples)
                    begin
                       captured[captured_count] = demodulated;
                       captured_count = captured_count + 1;

                       if (captured_count == capture_samples)
                         begin
                            analyze_capture();
                            $finish;
                         end
                    end

                  audio_samples_seen = audio_samples_seen + 1;
               end
          end
     end:verify_audio
endmodule
