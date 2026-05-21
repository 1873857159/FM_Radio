/* ROM-backed audio source
 *
 * The source reads an 8-bit signed PCM clip from "audio_clip.mem" and expands
 * it to 16-bit samples. Each ROM value can be repeated for multiple audio
 * ticks so that a 16 kHz clip can be replayed on the 32 kHz system audio rate.
 */

module audio_rom_source
  #(parameter int sample_count  = 23388,   // number of ROM samples
    parameter int sample_repeat = 2,       // playback repeat factor
    parameter int start_addr    = 0)       // ROM start address
   (input  wire                reset,      // reset
    input  wire                clk,        // clock
    input  wire                en,         // audio sample enable
    output logic signed [15:0] data);      // PCM audio data

   localparam int addr_width   = (sample_count <= 1) ? 1 : $clog2(sample_count);
   localparam int repeat_width = (sample_repeat <= 1) ? 1 : $clog2(sample_repeat);

   (* ramstyle = "M9K" *)
   logic [7:0] rom [0:sample_count - 1];
   logic [addr_width - 1 : 0] addr;
   logic [repeat_width - 1 : 0] repeat_ctr;
   logic signed [7:0] sample_now;

   initial
     $readmemh("audio_clip.mem", rom);

   always_comb
     sample_now = $signed(rom[addr]);

   always_ff @(posedge clk or posedge reset)
     if (reset)
       begin
          addr       <= start_addr[addr_width - 1 : 0];
          repeat_ctr <= '0;
          data       <= '0;
       end
     else if (en)
       begin
          data <= {sample_now, 8'h00};

          if (sample_repeat == 1)
            begin
               if (addr == sample_count - 1)
                 addr <= '0;
               else
                 addr <= addr + 1'b1;
            end
          else if (repeat_ctr == sample_repeat - 1)
            begin
               repeat_ctr <= '0;
               if (addr == sample_count - 1)
                 addr <= '0;
               else
                 addr <= addr + 1'b1;
            end
          else
            repeat_ctr <= repeat_ctr + 1'b1;
       end
endmodule
