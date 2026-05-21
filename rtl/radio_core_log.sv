/* FM demodulation chain with logarithmic audio encoding */

module radio_core_log
  #(parameter width_dds    = 32,  // DDS accumulator width
    parameter width_cordic = 17,  // CORDIC width
    parameter R1           = 250, // carrier to broad-band frequency ratio
    parameter R2           = 30)  // broad-band to audio frequency ratio
   (input  wire                          reset,      // reset
    input  wire                          clk,        // clock
    input  wire                          en48m,      //  48 MHz first CIC filter clock enable
    input  wire                          en960k,     // 960 kHz base-band clock enable
    input  wire                          en32k,      //  32 kHz audio clock enable
    input  wire                          adc,        // broadcast signal from 1-bit ADC
    input  wire [width_dds - 1:0]        K,          // phase constant for DDS
    output wire signed [15:0]            demodulated,// demodulated PCM audio
    output wire        [7:0]             log_code,   // logarithmic audio code
    output reg                           log_valid); // code valid strobe

   reg [1:0] log_pipe_primed;

   radio_core
     #(.width_dds   (width_dds),
       .width_cordic(width_cordic),
       .R1          (R1),
       .R2          (R2))
   inst_radio_core
     (.reset,
      .clk,
      .en48m,
      .en960k,
      .en32k,
      .adc,
      .K,
      .demodulated);

   log_encoder
     #(.width_in($bits(demodulated)))
   inst_log_encoder
     (.reset,
      .clk,
      .en (en32k),
      .in (demodulated),
      .out(log_code));

   always @(posedge clk)
     begin:valid_pipeline
        if (reset)
          begin
             log_pipe_primed <= '0;
             log_valid       <= 1'b0;
          end
        else if (en32k)
          begin
             log_valid       <= &log_pipe_primed;
             log_pipe_primed <= {log_pipe_primed[0], 1'b1};
          end
        else
          log_valid <= 1'b0;
     end:valid_pipeline
endmodule
