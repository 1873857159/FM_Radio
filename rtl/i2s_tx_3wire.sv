/* Three-wire mono-to-stereo I2S transmitter
 *
 * This version does not require an external audio master clock. Instead it
 * runs entirely from the 240 MHz system clock and uses an exact fractional
 * divider:
 *
 *   240 MHz * 64 / 3750 = 4.096 MHz  (BCK toggle rate)
 *   BCK = 2.048 MHz
 *   LRCK = 2.048 MHz / 64 = 32 kHz
 *
 * The mono input sample is duplicated to both I2S channels.
 */

module i2s_tx_3wire
  #(parameter width      = 16,   // PCM width
    parameter slot_width = 32,   // I2S slot width per channel
    parameter tick_num   = 64,   // fractional divider numerator
    parameter tick_den   = 3750) // fractional divider denominator
   (input  wire                    reset,      // reset
    input  wire                    clk,        // 240 MHz system clock
    input  wire                    sample_stb, // new mono sample
    input  wire signed [width-1:0] sample,     // mono PCM sample
    output logic                   bck,        // I2S bit clock
    output logic                   lrck,       // I2S left/right clock
    output logic                   din);       // I2S serial data

   localparam int unsigned frame_bits = 2 * slot_width;
   localparam int unsigned acc_width  = $clog2(tick_den + tick_num);
   localparam int unsigned bit_width  = $clog2(frame_bits);
   typedef logic [acc_width:0] acc_t;
   localparam acc_t tick_num_value = acc_t'(tick_num);
   localparam acc_t tick_den_value = acc_t'(tick_den);

   logic signed [width-1:0] pending_sample;
   logic [acc_width-1:0]    tick_accum;
   logic [bit_width-1:0]    bit_index;
   logic [acc_width:0]      tick_sum;
   logic [acc_width:0]      tick_wrap;
   logic                    tick_fire;
   logic                    tick_fire_r;
   logic [acc_width-1:0]    tick_next;
   logic [frame_bits-1:0]   shift_reg;

   function automatic logic [slot_width - 1:0] slot_word(
     input logic signed [width-1:0] word);
      begin
         slot_word = {1'b0, word, {(slot_width - width - 1){1'b0}}};
      end
   endfunction

   function automatic logic [frame_bits - 1:0] frame_word(
     input logic signed [width-1:0] mono_word);
      begin
         frame_word = {slot_word(mono_word), slot_word(mono_word)};
      end
   endfunction

   assign tick_sum  = {1'b0, tick_accum} + tick_num_value;
   assign tick_fire = (tick_sum >= tick_den_value);
   assign tick_wrap = tick_sum - tick_den_value;
   assign tick_next = tick_fire ? tick_wrap[acc_width-1:0] : tick_sum[acc_width-1:0];
   assign din       = shift_reg[frame_bits - 1];

   always_ff @(posedge clk or posedge reset)
     if (reset)
       pending_sample <= '0;
     else if (sample_stb)
       pending_sample <= sample;

   always_ff @(posedge clk or posedge reset)
     if (reset)
       begin
          tick_accum  <= '0;
          tick_fire_r <= 1'b0;
       end
     else
       begin
          tick_accum  <= tick_next;
          tick_fire_r <= tick_fire;
       end

   always_ff @(posedge clk or posedge reset)
     if (reset)
       begin
          bck         <= 1'b0;
          lrck        <= 1'b0;
          bit_index   <= frame_bits - 1;
          shift_reg   <= '0;
       end
     else
       begin
          if (tick_fire_r)
            begin
               bck <= ~bck;

               if (bck)
                 begin
                    if (bit_index == frame_bits - 1)
                      begin
                         bit_index <= '0;
                         shift_reg <= frame_word(pending_sample);
                         lrck      <= 1'b0;
                      end
                    else
                      begin
                         bit_index <= bit_index + 1'b1;
                         shift_reg <= {shift_reg[frame_bits - 2 : 0], 1'b0};

                         if (bit_index == slot_width - 1)
                           lrck <= 1'b1;
                      end
                 end
            end
       end
endmodule
