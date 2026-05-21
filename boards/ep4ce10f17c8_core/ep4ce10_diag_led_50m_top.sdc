create_clock -name clk50m -period 20.000000 [get_ports clk50m]
derive_clock_uncertainty
set_false_path -from [get_ports {reset_n}]
