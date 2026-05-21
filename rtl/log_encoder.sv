/* ROM-based logarithmic audio encoder
 *
 * The module converts 16-bit signed PCM samples to an 8-bit logarithmic
 * code word.  The most-significant bit stores the sign, while the lower
 * seven bits are looked up from a ROM initialized by 'log_encoder_rom.hex'.
 */

module log_encoder
  #(parameter width_in = 16)
   (input  wire                       reset, // reset
    input  wire                       clk,   // clock
    input  wire                       en,    // clock enable
    input  wire signed [width_in-1:0] in,    // signed PCM input
    output reg         [7:0]          out);  // logarithmic output code

   localparam int width_mag      = width_in - 1;
   localparam int width_rom      = 12;
   localparam int rom_depth      = 1 << width_rom;
   localparam int rom_max_input  = (1 << width_mag) - 4;
   localparam [width_rom - 1:0] rom_max_addr = {width_rom{1'b1}};

   reg  [width_mag - 1:0] magnitude;
   reg  [width_rom - 1:0] rom_addr;
   reg  [width_rom:0]     scaled_magnitude;
   reg  [width_mag:0]     magnitude_rounded;
   reg                    sign_reg;
   reg  [6:0]             rom [0:rom_depth - 1];
   reg  [6:0]             rom_q;

   always @*
     begin:abs_value
        scaled_magnitude = '0;
        magnitude_rounded = '0;

        if (!in[width_in - 1])
          magnitude = in[width_mag - 1:0];
        else if (in == {1'b1, {(width_in - 1){1'b0}}})
          magnitude = {width_mag{1'b1}};
        else
          magnitude = (~in[width_mag - 1:0]) + 1'b1;

        if (magnitude >= rom_max_input)
          rom_addr = rom_max_addr;
        else
          begin
             magnitude_rounded = {1'b0, magnitude} + 4'd4;
             scaled_magnitude  = magnitude_rounded[width_mag:3];
             rom_addr         = scaled_magnitude[width_rom - 1:0];
          end
     end:abs_value

   initial
     $readmemb("log_encoder_rom.mem", rom);

   always @(posedge clk)
     begin:sim_rom_read
        if (en)
          rom_q <= rom[rom_addr];
     end:sim_rom_read

   always @(posedge clk)
     begin:encode
        if (reset)
          begin
             sign_reg <= 1'b0;
             out      <= '0;
          end
        else if (en)
          begin
             sign_reg <= in[width_in - 1];
             out      <= {sign_reg, rom_q};
          end
     end:encode
endmodule
