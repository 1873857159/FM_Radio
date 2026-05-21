/* Radio core */

module radio_core
  #(parameter width_dds    = 32,                            // DDS accumulator width
    parameter width_cordic = 17,                            // CORDIC width
    parameter R1           = 250,                           // carrier to broad-band frequency ratio
    parameter R2           = 30)                            // broad-band to audio frequency ratio
   (input  wire                             reset,          // reset
    input  wire                             clk,            // clock
    input  wire                             en48m,          //  48 MHz first CIC filter clock enable
    input  wire                             en960k,         // 960 kHz base-band clock enable
    input  wire                             en32k,          //  32 kHz audio clock enable
    input  wire                             adc,            // broadcast signal from 1-bit ADC
    input  wire        [width_dds - 1:0]    K,              // phase constant for DDS
    output wire signed [15:0]               demodulated);   // demodulated signal

   localparam R1a = 5;      // first CIC filter stage
   localparam R1b = R1 / 5; // second CIC filter stage

   wire                                                    adc_s;    // synchronized broadcast signal from 1-bit ADC
   wire signed [width_dds - 1:0]                           phase;    // DDS phase
   wire signed [1:0]                                       I, Q;     // I/Q
   wire signed [2 + $clog2(R1a**3) - 1:0]                  If1, Qf1; // filtered I/Q, first stage
   wire signed [2 + $clog2(R1a**3) + $clog2(R1b**3) - 1:0] If2, Qf2; // filtered I/Q, second stage
   logic                                                   en960k_cordic; // first delayed 960 kHz enable for discriminator chain
   logic                                                   en960k_disc;   // second delayed 960 kHz enable for CORDIC evaluation
   logic signed [width_cordic - 1:0]                       If2_cordic, Qf2_cordic; // first registered CORDIC inputs
   logic signed [width_cordic - 1:0]                       If2_disc, Qf2_disc; // second registered CORDIC inputs
   wire signed [width_cordic - 1:0]                    cordic_phase; // CORDIC phase
   wire signed [width_cordic - 1:0]              differentiator_out; // differentiator output
   wire signed [width_cordic + $clog2(R2**3) - 1:0]   demodulated_f; // filtered demodulated

   /**************************************************
    * DDS
    **************************************************/

   dds
     #(.width(width_dds))
   inst_dds
     (.reset,
      .clk(clk),
      .K,
      .phase);

   /**************************************************
    * Carrier to I/Q conversion
    **************************************************/

   synchronizer sync_adc
     (.reset,
      .clk(clk),
      .en(1'b1),
      .in (adc),
      .out(adc_s));

   iq_modulator inst_iq_modulator
     (.clk  (clk),
      .adc  (adc_s),
      .phase(phase[$left(phase)-:2]),
      .I,
      .Q);

   /**************************************************
    * Base-band filters
    **************************************************/

   /* first stage */
   cic_3_filter
     #(.R    (R1a),
       .width($bits(I)))
   filter_I1
     (.reset,
      .clk   (clk),
      .en_in (1'b1),
      .en_out(en48m),
      .in    (I),
      .out   (If1));

   cic_3_filter
     #(.R    (R1a),
       .width($bits(Q)))
   filter_Q1
     (.reset,
      .clk   (clk),
      .en_in (1'b1),
      .en_out(en48m),
      .in    (Q),
      .out   (Qf1));

   /* second stage */
   cic_3_filter
     #(.R    (R1b),
       .width($bits(If1)))
   filter_I2
     (.reset,
      .clk   (clk),
      .en_in (en48m),
      .en_out(en960k),
      .in    (If1),
      .out   (If2));

   cic_3_filter
     #(.R    (R1b),
       .width($bits(Qf1)))
   filter_Q2
     (.reset,
      .clk   (clk),
      .en_in (en48m),
      .en_out(en960k),
      .in    (Qf1),
      .out   (Qf2));

   /**************************************************
    * Frequency discriminator
    **************************************************/

   // Capture the decimated I/Q samples and the corresponding enable locally.
   // Two short local stages are easier to place than one long CIC-to-CORDIC
   // path plus the original high-fanout enable path.
   always_ff @(posedge clk or posedge reset)
     if (reset)
       begin
          en960k_cordic <= 1'b0;
          en960k_disc   <= 1'b0;
          If2_cordic    <= '0;
          Qf2_cordic    <= '0;
          If2_disc      <= '0;
          Qf2_disc      <= '0;
       end
     else
       begin
          en960k_cordic <= en960k;
          en960k_disc   <= en960k_cordic;

          if (en960k)
            begin
               If2_cordic <= If2[$left(If2) - 1 -: width_cordic];
               Qf2_cordic <= Qf2[$left(Qf2) - 1 -: width_cordic];
            end

          if (en960k_cordic)
            begin
               If2_disc <= If2_cordic;
               Qf2_disc <= Qf2_cordic;
            end
       end

   /* Connect x0/y0 with double magnitude of If/Qf in order to
    * compensate the conversion gain of 1/2.
    * This improves the S/N ratio of the CORDIC unit.
    */
   cordic
     #(.vectoring(1),
       .width    (width_cordic))
   inst_cordic
     (.reset,
      .clk(clk),
      .en(en960k_disc),
      .x0 (If2_disc),
      .y0 (Qf2_disc),
      .z0 ('0),
      .x  (/*open*/),
      .y  (/*open*/),
      .z  (cordic_phase));

   differentiator
     #(.width(width_cordic))
   inst_differentiator
     (.reset,
      .clk(clk),
      .en(en960k_disc),
      .in(cordic_phase),
      .out(differentiator_out));

   /**************************************************
    * Audio filters
    **************************************************/

   cic_3_filter
     #(.R    (R2),
       .width(width_cordic))
   filter_audio
     (.reset,
      .clk   (clk),
      .en_in (en960k_disc),
      .en_out(en32k),
      .in    (differentiator_out),
      .out   (demodulated_f));

   /* Compensate residual loopback gain loss by taking one extra bit. */
   assign demodulated = demodulated_f[$left(demodulated_f) - 3 -: 16];
endmodule
