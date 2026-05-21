/* Mono PCM sample bridge for slow-rate clock-domain crossing
 *
 * A 32 kHz sample stream is transferred from the radio-core clock domain to
 * the audio-interface clock domain with a toggle handshake. The payload is
 * held stable until the destination acknowledges it.
 */

module audio_sample_bridge
  #(parameter width = 16)
   (input  wire                    reset,       // reset
    input  wire                    src_clk,     // source clock
    input  wire                    src_stb,     // source sample enable
    input  wire signed [width-1:0] src_sample,  // source sample
    input  wire                    dst_clk,     // destination clock
    output logic                   dst_stb,     // destination sample enable
    output logic signed [width-1:0] dst_sample);// destination sample

   logic signed [width-1:0] sample_hold;
   logic                    req_toggle;
   logic                    ack_toggle;
   logic [1:0]              ack_sync;
   logic [1:0]              req_sync;

   always_ff @(posedge src_clk or posedge reset)
     if (reset)
       begin
          sample_hold <= '0;
          req_toggle  <= 1'b0;
          ack_sync    <= '0;
       end
     else
       begin
          ack_sync <= {ack_sync[0], ack_toggle};

          if (src_stb && (ack_sync[1] == req_toggle))
            begin
               sample_hold <= src_sample;
               req_toggle  <= ~req_toggle;
            end
       end

   always_ff @(posedge dst_clk or posedge reset)
     if (reset)
       begin
          req_sync    <= '0;
          ack_toggle  <= 1'b0;
          dst_stb     <= 1'b0;
          dst_sample  <= '0;
       end
     else
       begin
          req_sync <= {req_sync[0], req_toggle};
          dst_stb  <= 1'b0;

          if (req_sync[1] != ack_toggle)
            begin
               dst_sample <= sample_hold;
               dst_stb    <= 1'b1;
               ack_toggle <= req_sync[1];
            end
       end
endmodule
