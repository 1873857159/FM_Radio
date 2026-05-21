/* 1-bit FM modulator
 *
 * The module keeps the latest PCM audio sample and converts it into
 * an instantaneous phase increment around the carrier frequency.
 * The MSB of the phase accumulator is used as a 1-bit FM waveform.
 */

module fm_modulator
  #(parameter width_phase = 32,              // NCO phase width
    parameter width_audio = 16,              // PCM sample width
    parameter int signed K_deviation = 32'd1342177) // 75 kHz @ 240 MHz
   (input  wire                           reset,     // reset
    input  wire                           clk,       // clock
    input  wire                           en_audio,  // audio sample enable
    input  wire [width_phase - 1 : 0]     K_carrier, // carrier phase increment
    input  wire signed [width_audio - 1 : 0] audio_in, // PCM audio sample
    output wire                           fm_out);   // 1-bit FM waveform

   logic signed [width_audio - 1 : 0]               audio_hold;
   logic signed [width_audio + width_phase - 1 : 0] deviation_product_reg;
   logic signed [width_phase : 0]                   phase_step_reg;
   logic [width_phase - 1 : 0]                      phase;

   always_ff @(posedge clk or posedge reset)
     if (reset)
       audio_hold <= '0;
     else if (en_audio)
       audio_hold <= audio_in;

   // Break the FM modulation path into pipeline stages so the 240 MHz
   // clock only sees a multiply, then an add, then the phase accumulator.
   always_ff @(posedge clk or posedge reset)
     if (reset)
       deviation_product_reg <= '0;
     else if (en_audio)
       deviation_product_reg <= audio_hold * K_deviation;

   always_ff @(posedge clk or posedge reset)
     if (reset)
       phase_step_reg <= $signed({1'b0, K_carrier});
     else if (en_audio)
       phase_step_reg <= $signed({1'b0, K_carrier})
                       + (deviation_product_reg >>> (width_audio - 1));

   always_ff @(posedge clk or posedge reset)
     if (reset)
       phase <= '0;
     else
       phase <= phase + phase_step_reg[width_phase - 1 : 0];

   assign fm_out = ~phase[$left(phase)];
endmodule
