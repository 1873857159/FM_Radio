/* PCM to PWM audio output
 *
 * The input PCM sample is latched at the audio sample rate and mapped
 * to an unsigned duty cycle. A simple RC low-pass filter can then be
 * used to recover the analog waveform from the PWM output.
 */

module pwm_audio
  #(parameter width_sample = 16,         // PCM sample width
    parameter width_pwm    = 8)          // PWM counter width
   (input  wire                              reset,     // reset
    input  wire                              clk,       // clock
    input  wire                              en_sample, // sample enable
    input  wire signed [width_sample - 1 : 0] sample,    // PCM audio sample
    output wire                              pwm_out);  // PWM bitstream

   logic signed [width_sample - 1 : 0] sample_hold;
   logic signed [width_sample     : 0] sample_biased;
   logic        [width_pwm - 1 : 0] pwm_counter;
   logic        [width_pwm - 1 : 0] duty_cycle;

   always_ff @(posedge clk or posedge reset)
     if (reset)
       begin
          sample_hold  <= '0;
          pwm_counter  <= '0;
       end
     else
       begin
          pwm_counter <= pwm_counter + 1'b1;
          if (en_sample)
            sample_hold <= sample;
       end

   always_comb
     begin
        sample_biased = $signed({sample_hold[$left(sample_hold)], sample_hold})
                      + (1 <<< (width_sample - 1));
        duty_cycle    = sample_biased[width_sample - 1 -: width_pwm];
     end

   assign pwm_out = (pwm_counter < duty_cycle);
endmodule
