/* On-chip FM audio loopback core for EP4CE6-class devices
 *
 * tone_source_1k -> fm_modulator -> radio_core -> pwm_audio
 *
 * This version replaces the original CORDIC-based test_tone generator with a
 * small ROM waveform source to make the loopback path fit smaller devices.
 */

module fm_loopback_ep4ce6_core
  #(parameter width_dds    = 32,             // DDS accumulator width
    parameter width_cordic = 17,             // CORDIC width
    parameter R1           = 250,            // carrier to broad-band frequency ratio
   parameter R2           = 30,             // broad-band to audio frequency ratio
    parameter [width_dds - 1 : 0] K_carrier = 32'h6AAAAAAA) // 100 MHz @ 240 MHz
   (input  wire                 reset_in,      // asynchronous reset
    input  wire                 clk240m,       // 240 MHz clock
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
   wire signed [15 : 0] audio_in;
   wire signed [15 : 0] audio_out;

   cru inst_cru
     (.reset_in,
      .reset_sync,
      .clk240m,
      .en48m,
      .en1m6,
      .en960k,
      .en32k);

   tone_source_1k inst_tone_source
     (.reset(reset_sync),
      .clk  (clk240m),
      .en   (en32k),
      .data (audio_in));

   fm_modulator
     #(.width_phase(width_dds),
       .width_audio($bits(audio_in)))
   inst_fm_modulator
     (.reset    (reset_sync),
      .clk      (clk240m),
      .en_audio (en32k),
      .K_carrier(K_carrier),
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

   assign en32k_dbg   = en32k;
   assign audio_in_dbg  = audio_in;
   assign audio_out_dbg = audio_out;
endmodule
