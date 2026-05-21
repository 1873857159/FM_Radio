create_clock -name clk240m -period 4.166667 [get_ports clk240m]
derive_clock_uncertainty
set_false_path -from [get_ports {reset_n}]
