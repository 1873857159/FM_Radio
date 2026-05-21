/* On-chip FM audio loopback core using a ROM speech clip
 *
 * audio_rom_source -> fm_modulator -> radio_core -> pwm_audio
 */

module fm_loopback_audio_rom_core
  #(parameter width_dds    = 32,             // DDS accumulator width
    parameter width_fm     = 28,             // narrower FM source phase width for timing closure
    parameter width_cordic = 17,             // CORDIC width
    parameter R1           = 250,            // carrier to broad-band frequency ratio
    parameter R2           = 30,             // broad-band to audio frequency ratio
    parameter int audio_clk_div = R1 * R2,   // source-side divider for the ROM clock domain
    parameter int audio_sample_count = 23388,// ROM sample count for current speech clip
    parameter int audio_start_addr = 0,      // audio ROM start address
    parameter [width_dds - 1 : 0] K_carrier = 32'h6AAAAAAA) // 100 MHz @ 240 MHz
   (input  wire                 reset_in,      // asynchronous reset
    input  wire                 clk240m,       // 240 MHz clock
    input  wire                 clk_audio_src, // ROM source clock
    output wire                 fm_out,        // synthesized 1-bit FM waveform
    output wire                 pwm_out,       // PWM audio output
    output wire                 en32k_dbg,     // audio sample enable
    output wire signed [15 : 0] audio_in_dbg,  // source PCM audio
    output wire signed [15 : 0] audio_out_dbg);// demodulated PCM audio

   wire                 reset_sync;
   wire                 en48m;
   wire                 en1m6;
   wire                 en960k;
   wire                 en32k;
   wire                 en_audio_src;
   wire                 audio_in_stb;
   wire signed [15 : 0] audio_in_src;
   wire signed [15 : 0] audio_in;
   wire signed [15 : 0] audio_out;
   localparam [width_fm - 1 : 0] K_carrier_fm = K_carrier[width_dds - 1 -: width_fm];
   localparam int signed K_deviation_fm = 32'sd1073742 >>> (width_dds - width_fm); // 60 kHz @ 240 MHz

   cru inst_cru
     (.reset_in,
      .reset_sync,
      .clk240m,
      .en48m,
      .en1m6,
      .en960k,
      .en32k);

   clock_divider
     #(.M(audio_clk_div))
   inst_clk_audio_src
     (.reset(reset_sync),
      .clk  (clk_audio_src),
      .en_i (1'b1),
      .en_o (en_audio_src));

   audio_rom_source
     #(.sample_count(audio_sample_count),
       .start_addr  (audio_start_addr))
   inst_audio_rom_source
     (.reset(reset_sync),
      .clk  (clk_audio_src),
      .en   (en_audio_src),
      .data (audio_in_src));

   audio_sample_bridge inst_audio_bridge
     (.reset     (reset_sync),
      .src_clk   (clk_audio_src),
      .src_stb   (en_audio_src),
      .src_sample(audio_in_src),
      .dst_clk   (clk240m),
      .dst_stb   (audio_in_stb),
      .dst_sample(audio_in));

   fm_modulator
     #(.width_phase(width_fm),
      .width_audio($bits(audio_in)),
      .K_deviation(K_deviation_fm))
   inst_fm_modulator
     (.reset    (reset_sync),
      .clk      (clk240m),
      .en_audio (audio_in_stb),
      .K_carrier(K_carrier_fm),
      .audio_in (audio_in),
      .fm_out   (fm_out));

   radio_core
     #(.width_dds   (width_dds),
       .width_cordic(width_cordic),
       .R1          (R1),
       .R2          (R2))
   inst_radio_core
     (.reset      (reset_sync),
      .clk        (clk240m),
      .en48m,
      .en960k,
      .en32k,
      .adc        (fm_out),
      .K          (K_carrier),
      .demodulated(audio_out));

   pwm_audio inst_pwm_audio
     (.reset    (reset_sync),
      .clk      (clk240m),
      .en_sample(en32k),
      .sample   (audio_out),
      .pwm_out  (pwm_out));

   assign en32k_dbg    = en32k;
   assign audio_in_dbg = audio_in;
   assign audio_out_dbg = audio_out;
endmodule
