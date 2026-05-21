/* Lightweight clarity boost for speech playback.
 *
 * The filter adds a fraction of the first-order difference back into the
 * current sample. This gently lifts transient and high-frequency content
 * without changing the FM receiver core itself.
 */

module audio_clarity_boost
  #(parameter int width = 16,
    parameter int boost_shift = 1)  // 1 => add 1/2 of the first-order difference
   (input  wire                      reset,      // reset
    input  wire                      clk,        // clock
    input  wire                      en_sample,  // sample enable
    input  wire signed [width-1:0]   sample_in,  // input PCM sample
    output logic                     sample_stb, // delayed sample strobe
    output logic signed [width-1:0]  sample_out);// boosted PCM sample

   logic signed [width-1:0] current_sample;
   logic signed [width-1:0] prev_sample;
   logic                    sample_valid_d1;
   logic                    sample_valid_d2;
   logic                    sample_valid_d3;
   logic                    sample_valid_d4;
   logic signed [width-1:0] base_sample_d1;
   logic signed [width-1:0] diff_d1;
   logic signed [width-1:0] boosted_d2;

   always_ff @(posedge clk or posedge reset)
     if (reset)
       begin
          current_sample  <= '0;
          prev_sample     <= '0;
          sample_valid_d1 <= 1'b0;
          sample_valid_d2 <= 1'b0;
          sample_valid_d3 <= 1'b0;
          sample_valid_d4 <= 1'b0;
          sample_stb      <= 1'b0;
          base_sample_d1  <= '0;
          diff_d1         <= '0;
          boosted_d2      <= '0;
          sample_out      <= '0;
       end
     else
       begin
          sample_valid_d1 <= en_sample;
          sample_valid_d2 <= sample_valid_d1;
          sample_valid_d3 <= sample_valid_d2;
          sample_valid_d4 <= sample_valid_d3;
          sample_stb      <= sample_valid_d4;

          if (en_sample)
            begin
               prev_sample    <= current_sample;
               current_sample <= sample_in;
            end

          if (sample_valid_d1)
            begin
               base_sample_d1 <= current_sample;
               diff_d1        <= current_sample - prev_sample;
            end

          if (sample_valid_d2)
            boosted_d2 <= base_sample_d1 + (diff_d1 >>> boost_shift);

          if (sample_valid_d3)
            sample_out <= boosted_d2[width-1:0];
       end
endmodule
