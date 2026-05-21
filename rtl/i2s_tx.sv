/* Simple mono-to-stereo I2S transmitter
 *
 * Clock assumptions:
 * - clk is 12.288 MHz
 * - BCK is generated as 2.048 MHz (64 * 32 kHz)
 * - LRCK is generated as 32 kHz
 *
 * The mono input sample is duplicated to both channels.
 */

module i2s_tx
  #(parameter width      = 16, // PCM width
    parameter slot_width = 32) // I2S slot width per channel
   (input  wire                    reset,      // reset
    input  wire                    clk,        // 12.288 MHz master clock
    input  wire                    sample_stb, // new mono sample
    input  wire signed [width-1:0] sample,     // mono PCM sample
    output logic                   bck,        // I2S bit clock
    output logic                   lrck,       // I2S left/right clock
    output logic                   din);       // I2S serial data

   localparam int unsigned mclk_per_bclk = 6;
   localparam int unsigned half_div      = mclk_per_bclk / 2;
   localparam int unsigned frame_bits    = 2 * slot_width;

   logic signed [width-1:0] pending_sample;
   logic signed [width-1:0] left_sample;
   logic signed [width-1:0] right_sample;
   logic [$clog2(half_div)-1:0] half_counter;
   logic [$clog2(frame_bits)-1:0] bit_index;

   function automatic logic slot_bit(input logic signed [width-1:0] word,
                                     input int unsigned            slot_bit_index);
      begin
         if (slot_bit_index == 0)
           slot_bit = 1'b0;
         else if (slot_bit_index <= width)
           slot_bit = word[width - slot_bit_index];
         else
           slot_bit = 1'b0;
      end
   endfunction

   function automatic logic next_din(input logic signed [width-1:0] left_word,
                                     input logic signed [width-1:0] right_word,
                                     input int unsigned            index);
      begin
         if (index < slot_width)
           next_din = slot_bit(left_word, index);
         else
           next_din = slot_bit(right_word, index - slot_width);
      end
   endfunction

   always_ff @(posedge clk or posedge reset)
     if (reset)
       pending_sample <= '0;
     else if (sample_stb)
       pending_sample <= sample;

   always_ff @(posedge clk or posedge reset)
     if (reset)
       begin
          bck         <= 1'b0;
          lrck        <= 1'b0;
          din         <= 1'b0;
          half_counter <= '0;
          bit_index   <= '0;
          left_sample <= '0;
          right_sample <= '0;
       end
     else if (half_counter == half_div - 1)
       begin : advance_bclk
          logic [$clog2(frame_bits)-1:0] next_index;

          half_counter <= '0;
          bck <= ~bck;

          if (bck)
            begin
               if (bit_index == frame_bits - 1)
                 begin
                    next_index   = '0;
                    left_sample  <= pending_sample;
                    right_sample <= pending_sample;
                 end
               else
                 next_index = bit_index + 1'b1;

               bit_index <= next_index;
               lrck      <= (next_index >= slot_width);
               din       <= next_din(left_sample, right_sample, next_index);
            end
       end
     else
       half_counter <= half_counter + 1'b1;
endmodule
